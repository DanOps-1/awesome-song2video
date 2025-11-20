"""构建歌词与视频片段的时间线。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TypedDict
import re
from uuid import uuid4

import structlog

from src.infra.config.settings import get_settings
from src.pipelines.lyrics_ingest.transcriber import transcribe_with_timestamps
from src.services.matching.twelvelabs_client import client
from src.services.matching.query_rewriter import QueryRewriter


def calculate_overlap_ratio(start1: int, end1: int, start2: int, end2: int) -> float:
    """计算两个时间段的重叠比例。

    返回: 重叠部分占较短片段的比例 (0.0 到 1.0)
    """
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    overlap = max(0, overlap_end - overlap_start)

    if overlap == 0:
        return 0.0

    duration1 = end1 - start1
    duration2 = end2 - start2
    shorter_duration = min(duration1, duration2)

    if shorter_duration == 0:
        return 0.0

    return overlap / shorter_duration


@dataclass
class TimelineLine:
    text: str
    start_ms: int
    end_ms: int
    candidates: list[dict]


@dataclass
class TimelineResult:
    lines: list[TimelineLine] = field(default_factory=list)


class CandidateWithUsage(TypedDict):
    candidate: dict[str, int | float | str]
    usage_count: int
    score: float


class TimelineBuilder:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._use_mock_segments = not self._settings.tl_live_enabled
        self._candidate_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._logger = structlog.get_logger(__name__)
        self._split_pattern = re.compile(r"(?:\r?\n)+|[，,。！？!?；;…]")
        self._rewriter = QueryRewriter()
        # 追踪已使用的视频片段，避免重复
        # key = (video_id, start_ms, end_ms), value = 使用次数
        self._used_segments: dict[tuple[str, int, int], int] = {}
        # 重叠阈值：零容忍！任何重叠都不允许
        self._overlap_threshold = 0.0  # 任何重叠 > 0 就跳过

    async def build(self, audio_path: Path | None, lyrics_text: Optional[str]) -> TimelineResult:
        self._candidate_cache.clear()
        self._used_segments.clear()  # 重置已使用片段追踪
        segments: list[dict[str, Any]] = []
        if audio_path:
            raw_segments = await transcribe_with_timestamps(audio_path)
            segments = [dict(segment) for segment in raw_segments]
        elif lyrics_text:
            for idx, line in enumerate(lyrics_text.splitlines()):
                stripped = line.strip()
                if not stripped:
                    continue
                segments.append({"text": stripped, "start": float(idx), "end": float(idx + 1)})
        else:
            raise ValueError("必须提供音频或歌词")

        segments = self._explode_segments(segments)

        timeline = TimelineResult()
        for seg in segments:
            raw_text = str(seg.get("text", ""))
            text = raw_text.strip().strip("'\"")
            if not text:
                continue
            start_value = seg.get("start", 0)
            end_value = seg.get("end")
            start_ms = int(float(start_value) * 1000)
            if end_value is None:
                end_ms = start_ms + 1000
            else:
                end_ms = int(float(end_value) * 1000)
            # 获取更多候选片段以支持去重选择（增加到20个以提供更多去重空间）
            candidates = await self._get_candidates(text, limit=20)
            normalized = self._normalize_candidates(candidates, start_ms, end_ms)

            # 选择未使用或使用次数最少的片段
            selected_candidates = self._select_diverse_candidates(normalized, limit=3)

            # 标记第一个候选片段为已使用（渲染时默认使用第一个）
            if selected_candidates:
                first = selected_candidates[0]
                segment_key = (
                    str(first.get("source_video_id")),
                    int(first.get("start_time_ms", 0)),
                    int(first.get("end_time_ms", 0)),
                )
                self._used_segments[segment_key] = self._used_segments.get(segment_key, 0) + 1

            timeline.lines.append(
                TimelineLine(
                    text=text,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    candidates=selected_candidates,
                )
            )
        return timeline

    def _normalize_candidates(
        self, raw_candidates: list[dict[str, int | float | str]], start_ms: int, end_ms: int
    ) -> list[dict[str, int | float | str]]:
        def _candidate_defaults(candidate: dict[str, int | float | str]) -> dict[str, int | float | str]:
            # 🔧 修复: 从 API 返回片段的中间位置截取，以获得最匹配的画面
            # 原因：AI 匹配的精彩画面往往在片段中间，而不是开头
            api_start = int(candidate.get("start", start_ms))
            api_end = int(candidate.get("end", end_ms))
            lyric_duration = end_ms - start_ms

            # 计算API片段的中间位置
            api_duration = api_end - api_start
            api_middle = api_start + (api_duration // 2)

            # 从中间位置向前偏移一半歌词时长，使歌词时长居中
            clip_start = api_middle - (lyric_duration // 2)
            clip_end = clip_start + lyric_duration

            # 确保不会超出原始片段范围
            if clip_start < api_start:
                clip_start = api_start
                clip_end = min(api_start + lyric_duration, api_end)
            elif clip_end > api_end:
                clip_end = api_end
                clip_start = max(api_end - lyric_duration, api_start)

            return {
                "id": str(uuid4()),
                "source_video_id": candidate.get("video_id", self._settings.fallback_video_id),
                "start_time_ms": clip_start,              # 从中间位置开始截取
                "end_time_ms": clip_end,                  # 保持歌词时长
                "score": candidate.get("score", 0.0),
                # 保留原始数据供参考
                "api_start_ms": api_start,
                "api_end_ms": api_end,
                "api_middle_ms": api_middle,
                "lyric_start_ms": start_ms,
                "lyric_end_ms": end_ms,
            }

        if raw_candidates:
            return [_candidate_defaults(c) for c in raw_candidates]
        return [
            {
                "id": str(uuid4()),
                "source_video_id": self._settings.fallback_video_id,
                "start_time_ms": start_ms,
                "end_time_ms": end_ms,
                "score": 0.0,
            }
        ]

    async def _get_candidates(self, text: str, limit: int) -> list[dict[str, Any]]:
        """
        获取候选片段，支持两种策略：

        策略1: 强制改写模式 (QUERY_REWRITE_MANDATORY=true)
        1. AI改写（第1次） → 查询
        2. 无候选 → AI改写（第2次，通用化） → 重试
        3. 仍无候选 → AI改写（第3次，极简化） → 重试
        4. 仍无候选 → 返回空（使用fallback）

        策略2: 按需改写模式 (QUERY_REWRITE_MANDATORY=false，默认)
        1. 原始查询 → 有候选 → 使用
        2. 原始查询 → 无候选 → AI改写（第1次） → 重试
        3. 仍无候选 → AI改写（第2次，通用化） → 重试
        4. 仍无候选 → AI改写（第3次，极简化） → 重试
        5. 仍无候选 → 返回空（使用fallback）
        """
        key = (text, limit)
        if key not in self._candidate_cache:
            candidates: list[dict[str, Any]] = []
            query_text = text

            # 如果启用了改写且配置为强制改写，第一次查询就改写
            if self._rewriter._enabled and self._settings.query_rewrite_mandatory:
                self._logger.info(
                    "timeline_builder.mandatory_rewrite",
                    original=text[:30],
                    message="强制改写模式，跳过原始查询",
                )
                # 直接进入改写流程，从 attempt=0 开始
                query_text = await self._rewriter.rewrite(text, attempt=0)
                self._logger.info(
                    "timeline_builder.mandatory_rewrite_query",
                    original=text[:30],
                    rewritten=query_text[:30],
                )
                candidates = await client.search_segments(query_text, limit=limit)

                # 如果第一次改写就成功，记录日志
                if candidates:
                    self._logger.info(
                        "timeline_builder.mandatory_rewrite_success",
                        original=text[:30],
                        rewritten=query_text[:50],
                        count=len(candidates),
                    )
            else:
                # 第一步：尝试原始查询
                candidates = await client.search_segments(text, limit=limit)

            # 第二步：如果无候选且启用了改写，智能重试改写
            if not candidates and self._rewriter._enabled:
                max_attempts = self._settings.query_rewrite_max_attempts
                # 如果已经执行过强制改写，从 attempt=1 开始（跳过第一次）
                start_attempt = 1 if self._settings.query_rewrite_mandatory else 0

                for attempt in range(start_attempt, max_attempts):
                    self._logger.info(
                        "timeline_builder.fallback_to_rewrite",
                        original=text[:30],
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                    )

                    rewritten_query = await self._rewriter.rewrite(text, attempt=attempt)

                    # 如果改写后的查询不同，则重试
                    if rewritten_query != text and rewritten_query != query_text:
                        candidates = await client.search_segments(rewritten_query, limit=limit)
                        self._logger.info(
                            "timeline_builder.rewrite_result",
                            original=text[:30],
                            rewritten=rewritten_query[:30],
                            attempt=attempt + 1,
                            count=len(candidates),
                        )

                        # 如果找到候选，立即退出循环
                        if candidates:
                            self._logger.info(
                                "timeline_builder.rewrite_success",
                                original=text[:30],
                                attempt=attempt + 1,
                                final_query=rewritten_query[:50],
                                count=len(candidates),
                            )
                            break
                    else:
                        self._logger.warning(
                            "timeline_builder.rewrite_identical",
                            original=text[:30],
                            attempt=attempt + 1,
                        )

            self._candidate_cache[key] = candidates

        candidates = [candidate.copy() for candidate in self._candidate_cache[key]]
        count = len(candidates)
        log_method = self._logger.warning if count == 0 else self._logger.info
        log_method(
            "timeline_builder.candidates",
            text_preview=text[:30],
            count=count,
            use_mock=self._use_mock_segments,
        )
        return candidates

    def _select_diverse_candidates(
        self, candidates: list[dict[str, int | float | str]], limit: int
    ) -> list[dict[str, int | float | str]]:
        """
        从候选列表中选择多样化的片段，尽量避免重复使用相同的视频片段。

        策略：
        1. 优先选择未使用过的片段
        2. 如果没有未使用的片段，允许使用次数最少的片段（避免完全无片段可用）
        3. 按评分排序选择最佳的
        """
        if not candidates:
            return []

        # 为每个候选片段计算使用次数和评分，并检测时间重叠
        candidates_with_usage: list[CandidateWithUsage] = []
        for candidate in candidates:
            video_id = str(candidate.get("source_video_id", ""))
            start_ms = int(candidate.get("start_time_ms", 0))
            end_ms = int(candidate.get("end_time_ms", 0))

            # 检查是否与已使用的片段有任何重叠（零容忍！）
            has_overlap = False
            overlapping_segment = None
            for used_key in self._used_segments.keys():
                used_video_id, used_start, used_end = used_key
                if used_video_id == video_id:
                    overlap_ratio = calculate_overlap_ratio(start_ms, end_ms, used_start, used_end)
                    if overlap_ratio > 0:  # 任何重叠都不允许！
                        has_overlap = True
                        overlapping_segment = used_key
                        self._logger.warning(
                            "timeline_builder.overlap_rejected",
                            video_id=video_id,
                            start_ms=start_ms,
                            end_ms=end_ms,
                            overlapping_with=overlapping_segment,
                            overlap_ratio=round(overlap_ratio, 3),
                            message="零容忍策略：直接剔除任何有重叠的片段",
                        )
                        break

            # 如果有任何重叠，直接跳过该片段（零容忍！）
            if has_overlap:
                continue  # 直接剔除，不添加到候选列表

            # 检查精确匹配
            segment_key = (video_id, start_ms, end_ms)
            usage_count = self._used_segments.get(segment_key, 0)

            candidates_with_usage.append({
                "candidate": candidate,
                "usage_count": usage_count,
                "score": float(candidate.get("score", 0.0)),
            })

        # 排序策略：
        # 1. 使用次数少的优先（usage_count升序）
        # 2. 相同使用次数时，score高的优先（score降序）
        candidates_with_usage.sort(key=lambda x: (x["usage_count"], -x["score"]))

        # 提取候选片段并限制数量
        selected: list[dict[str, int | float | str]] = [
            item["candidate"] for item in candidates_with_usage[:limit]
        ]

        # 记录选中的片段详细信息
        for idx, item in enumerate(candidates_with_usage[:limit]):
            candidate = item["candidate"]
            self._logger.info(
                "timeline_builder.selected_clip",
                index=idx + 1,
                video_id=candidate.get("source_video_id"),
                start_ms=candidate.get("start_time_ms"),
                end_ms=candidate.get("end_time_ms"),
                duration_ms=candidate.get("end_time_ms", 0) - candidate.get("start_time_ms", 0),
                score=candidate.get("score"),
                usage_count=item["usage_count"],
            )

        # 记录日志
        if candidates_with_usage:
            first_usage = candidates_with_usage[0]["usage_count"]
            unused_count = sum(1 for item in candidates_with_usage if item["usage_count"] == 0)

            if first_usage > 0:
                self._logger.warning(
                    "timeline_builder.reuse_segment",
                    total_candidates=len(candidates),
                    unused_count=unused_count,
                    selected_usage_count=first_usage,
                    message=f"候选不足，重复使用片段（已使用{first_usage}次）",
                )
            else:
                self._logger.info(
                    "timeline_builder.diversity_selection",
                    total_candidates=len(candidates),
                    unused_count=unused_count,
                    selected_count=len(selected),
                    message=f"从{unused_count}个未使用片段中选择了{len(selected)}个",
                )

        return selected

    def _explode_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        exploded: list[dict[str, Any]] = []
        for seg in segments:
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            pieces = [piece.strip() for piece in self._split_pattern.split(text) if piece and piece.strip()]
            if len(pieces) <= 1:
                exploded.append(seg)
                continue
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", start + 1.0))
            if end <= start:
                end = start + 1.0
            duration = end - start
            total_chars = sum(len(piece) for piece in pieces) or len(pieces)
            cursor = start
            for idx, piece in enumerate(pieces):
                ratio = len(piece) / total_chars if total_chars else 1.0 / len(pieces)
                chunk_duration = duration * ratio
                chunk_end = end if idx == len(pieces) - 1 else cursor + chunk_duration
                exploded.append(
                    {
                        **seg,
                        "text": piece,
                        "start": cursor,
                        "end": chunk_end,
                    }
                )
                cursor = chunk_end
        return exploded

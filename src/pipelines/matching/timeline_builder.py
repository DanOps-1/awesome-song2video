"""构建歌词与视频片段的时间线。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, TypedDict
import re
from uuid import uuid4

# 进度回调类型: async def callback(progress: float) -> None
ProgressCallback = Callable[[float], Coroutine[Any, Any, None]]

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

    def _is_non_lyric_text(self, text: str) -> bool:
        """
        判断文本是否为非歌词内容（如作词、作曲、编曲等标注）。

        识别模式：
        - "作词 XX" / "词 XX"
        - "作曲 XX" / "曲 XX"
        - "编曲 XX" / "编 XX"
        - "演唱 XX" / "唱 XX"
        - "制作 XX"
        - 纯英文的 credits（如 "Lyrics by", "Music by"）
        """
        text = text.strip()

        # 中文 credits 模式
        non_lyric_patterns = [
            r'^作词[\s:：]',
            r'^词[\s:：]',
            r'^作曲[\s:：]',
            r'^曲[\s:：]',
            r'^编曲[\s:：]',
            r'^编[\s:：]',
            r'^演唱[\s:：]',
            r'^唱[\s:：]',
            r'^制作[\s:：]',
            r'^监制[\s:：]',
            r'^混音[\s:：]',
            r'^母带[\s:：]',
        ]

        # 英文 credits 模式
        english_patterns = [
            r'(?i)^lyrics\s+by',
            r'(?i)^music\s+by',
            r'(?i)^composed\s+by',
            r'(?i)^arranged\s+by',
            r'(?i)^performed\s+by',
            r'(?i)^produced\s+by',
        ]

        all_patterns = non_lyric_patterns + english_patterns

        for pattern in all_patterns:
            if re.search(pattern, text):
                return True

        return False

    def _get_audio_duration(self, audio_path: Path) -> int:
        """使用 ffprobe 获取音频文件时长（毫秒）。"""
        import subprocess

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path.as_posix(),
        ]
        try:
            result = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(float(result.stdout.strip()) * 1000)
        except Exception as exc:
            self._logger.warning("ffprobe.audio_duration_failed", path=audio_path, error=str(exc))
        return 0

    def _split_by_duration(self, segments: list[dict[str, Any]], max_duration: float = 12.0) -> list[dict[str, Any]]:
        """将过长的片段按时长切分为更小的片段，以增加画面丰富度。"""
        split_segments: list[dict[str, Any]] = []
        for seg in segments:
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            duration = end - start
            
            if duration <= max_duration:
                split_segments.append(seg)
                continue
                
            # 计算需要切分的块数
            num_chunks = int(duration // max_duration) + 1
            chunk_duration = duration / num_chunks
            
            text = seg.get("text", "")
            base_prompt = seg.get("search_prompt", "")
            
            for i in range(num_chunks):
                chunk_start = start + (i * chunk_duration)
                chunk_end = chunk_start + chunk_duration
                
                # 创建新片段，复制元数据
                new_seg = seg.copy()
                new_seg["start"] = chunk_start
                new_seg["end"] = chunk_end
                
                # 如果有搜索提示词，添加变化以增加多样性
                if base_prompt:
                    new_seg["search_prompt"] = f"{base_prompt}, scene {i+1}"
                
                # 对于长文本（如 Credits），后续片段可以不再显示文本，或者保留
                # 这里为了简单，保留文本，但画面会变
                
                split_segments.append(new_seg)
                
            self._logger.info(
                "timeline_builder.split_long_segment",
                original_text=text[:20],
                original_duration=round(duration, 2),
                chunks=num_chunks,
                message="长片段已切分",
            )
            
        return split_segments

    async def transcribe_only(
        self,
        audio_path: Path,
        language: str | None = None,
        prompt: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        """只进行 Whisper 识别，返回歌词片段列表（不进行视频匹配）。

        返回格式: [{"text": "歌词", "start": 开始秒, "end": 结束秒}, ...]
        """
        async def report_progress(progress: float) -> None:
            if on_progress:
                await on_progress(progress)

        await report_progress(5.0)  # 5%: 开始处理音频
        audio_duration_ms = self._get_audio_duration(audio_path)
        self._logger.info(
            "timeline_builder.audio_info",
            path=str(audio_path),
            duration_ms=audio_duration_ms
        )
        await report_progress(20.0)  # 20%: 开始 Whisper 识别

        raw_segments = await transcribe_with_timestamps(
            audio_path,
            language=language,
            prompt=prompt
        )
        segments = [dict(segment) for segment in raw_segments]

        await report_progress(80.0)  # 80%: Whisper 识别完成

        # 分割长片段
        segments = self._explode_segments(segments)

        await report_progress(100.0)  # 100%: 完成
        return segments

    async def match_videos_for_lines(
        self,
        lines: list[dict[str, Any]],
        audio_duration_ms: int = 0,
        on_progress: ProgressCallback | None = None,
    ) -> TimelineResult:
        """对已确认的歌词行进行视频匹配。

        Args:
            lines: 歌词行列表，格式 [{"text": "...", "start_ms": int, "end_ms": int}, ...]
            audio_duration_ms: 音频总时长（毫秒），用于填充尾部
            on_progress: 进度回调
        """
        self._candidate_cache.clear()
        self._used_segments.clear()

        async def report_progress(progress: float) -> None:
            if on_progress:
                await on_progress(progress)

        await report_progress(5.0)

        # 转换为内部 segments 格式
        segments: list[dict[str, Any]] = []
        for line in lines:
            segments.append({
                "text": line["text"],
                "start": line["start_ms"] / 1000.0,
                "end": line["end_ms"] / 1000.0,
            })

        # 标记非歌词内容
        for seg in segments:
            text = str(seg.get("text", "")).strip()
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            duration_s = end - start

            if self._is_non_lyric_text(text):
                if duration_s < 10.0:
                    seg["is_non_lyric"] = True
                else:
                    seg["is_non_lyric"] = False
                    seg["search_prompt"] = "cinematic music video intro, atmospheric, slow motion"

        # 切分长片段
        segments = self._split_by_duration(segments, max_duration=12.0)
        segments.sort(key=lambda x: float(x.get("start", 0)))

        # 进行视频匹配（复用 build 方法的匹配逻辑）
        timeline = TimelineResult()
        cursor_ms = 0
        total_segments = len(segments)

        for seg_idx, seg in enumerate(segments):
            if total_segments > 0:
                match_progress = 10.0 + (seg_idx / total_segments) * 85.0
                await report_progress(match_progress)

            raw_text = str(seg.get("text", ""))
            text = raw_text.strip().strip("'\"")
            if not text:
                continue

            start_ms = int(float(seg.get("start", 0)) * 1000)
            end_ms = int(float(seg.get("end", 0)) * 1000)

            # 间隙处理
            if cursor_ms > 0 and start_ms > cursor_ms:
                gap = start_ms - cursor_ms
                if gap > 2000:
                    gap_prompt = "atmospheric music video, cinematic scenes, instrumental, no lyrics"
                    gap_candidates = await self._get_candidates(gap_prompt, limit=20)
                    normalized_gap = self._normalize_candidates(gap_candidates, cursor_ms, start_ms)
                    selected_gap = self._select_diverse_candidates(normalized_gap, limit=3)
                    if not selected_gap:
                        selected_gap = [{
                            "id": str(uuid4()),
                            "source_video_id": self._settings.fallback_video_id,
                            "start_time_ms": cursor_ms,
                            "end_time_ms": start_ms,
                            "score": 0.0,
                        }]
                    for candidate in selected_gap:
                        segment_key = (
                            str(candidate.get("source_video_id")),
                            int(candidate.get("start_time_ms", 0)),
                            int(candidate.get("end_time_ms", 0)),
                        )
                        self._used_segments[segment_key] = self._used_segments.get(segment_key, 0) + 1
                    timeline.lines.append(TimelineLine(
                        text="(Instrumental)",
                        start_ms=cursor_ms,
                        end_ms=start_ms,
                        candidates=selected_gap
                    ))
                else:
                    start_ms = cursor_ms

            # 处理当前片段
            if seg.get("is_non_lyric", False):
                candidates = []
            else:
                search_query = seg.get("search_prompt", text)
                candidates = await self._get_candidates(search_query, limit=20)

            normalized = self._normalize_candidates(candidates, start_ms, end_ms)
            selected_candidates = self._select_diverse_candidates(normalized, limit=3)

            for candidate in selected_candidates:
                segment_key = (
                    str(candidate.get("source_video_id")),
                    int(candidate.get("start_time_ms", 0)),
                    int(candidate.get("end_time_ms", 0)),
                )
                self._used_segments[segment_key] = self._used_segments.get(segment_key, 0) + 1

            timeline.lines.append(TimelineLine(
                text=text,
                start_ms=start_ms,
                end_ms=end_ms,
                candidates=selected_candidates,
            ))
            cursor_ms = max(cursor_ms, end_ms)

        # 尾部填充
        if audio_duration_ms > cursor_ms + 1000:
            gap_start = cursor_ms
            gap_end = audio_duration_ms
            outro_prompt = "ending music video, fade out, cinematic, atmospheric"
            outro_candidates = await self._get_candidates(outro_prompt, limit=20)
            normalized_outro = self._normalize_candidates(outro_candidates, gap_start, gap_end)
            selected_outro = self._select_diverse_candidates(normalized_outro, limit=3)
            if not selected_outro:
                selected_outro = [{
                    "id": str(uuid4()),
                    "source_video_id": self._settings.fallback_video_id,
                    "start_time_ms": gap_start,
                    "end_time_ms": gap_end,
                    "score": 0.0,
                }]
            timeline.lines.append(TimelineLine(
                text="(Outro)",
                start_ms=gap_start,
                end_ms=gap_end,
                candidates=selected_outro
            ))

        await report_progress(100.0)
        return timeline

    async def build(
        self,
        audio_path: Path | None,
        lyrics_text: Optional[str],
        language: str | None = None,
        prompt: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> TimelineResult:
        """完整构建流程（兼容旧代码）：Whisper 识别 + 视频匹配。"""
        self._candidate_cache.clear()
        self._used_segments.clear()  # 重置已使用片段追踪
        segments: list[dict[str, Any]] = []
        audio_duration_ms = 0

        async def report_progress(progress: float) -> None:
            if on_progress:
                await on_progress(progress)

        if audio_path:
            await report_progress(5.0)  # 5%: 开始处理音频
            audio_duration_ms = self._get_audio_duration(audio_path)
            self._logger.info(
                "timeline_builder.audio_info",
                path=str(audio_path),
                duration_ms=audio_duration_ms
            )
            await report_progress(10.0)  # 10%: 开始 Whisper 识别
            raw_segments = await transcribe_with_timestamps(
                audio_path,
                language=language,
                prompt=prompt
            )
            segments = [dict(segment) for segment in raw_segments]
            await report_progress(30.0)  # 30%: Whisper 识别完成
        elif lyrics_text:
            for idx, line in enumerate(lyrics_text.splitlines()):
                stripped = line.strip()
                if not stripped:
                    continue
                segments.append({"text": stripped, "start": float(idx), "end": float(idx + 1)})
        else:
            raise ValueError("必须提供音频或歌词")

        segments = self._explode_segments(segments)
        
        # 标记非歌词内容（作词、作曲等 credits）
        # 策略更新：
        # 1. 短的 credits (< 10s) -> 标记为 non-lyric，使用 fallback
        # 2. 长的 credits (>= 10s) -> 视为 Intro/Interlude，改写 text 进行搜索
        non_lyric_count = 0
        for seg in segments:
            text = str(seg.get("text", "")).strip()
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            duration_s = end - start

            if self._is_non_lyric_text(text):
                if duration_s < 10.0:
                    seg["is_non_lyric"] = True
                    non_lyric_count += 1
                    self._logger.info(
                        "timeline_builder.mark_non_lyric",
                        text=text,
                        duration_s=round(duration_s, 2),
                        message="短 Credit 信息，标记为非歌词 (Fallback)",
                    )
                else:
                    # 长片段，即使包含 Credit 也不应该用黑屏 Fallback
                    # 改写为通用 Intro Prompt
                    seg["is_non_lyric"] = False
                    seg["search_prompt"] = "cinematic music video intro, atmospheric, slow motion"
                    self._logger.info(
                        "timeline_builder.convert_long_credit",
                        text=text,
                        duration_s=round(duration_s, 2),
                        message="长 Credit 片段，转换为 Intro 搜索",
                    )

        if non_lyric_count > 0:
            self._logger.info(
                "timeline_builder.non_lyric_summary",
                total_count=len(segments),
                non_lyric_count=non_lyric_count,
                lyric_count=len(segments) - non_lyric_count,
                message=f"发现 {non_lyric_count} 个短非歌词片段",
            )
            
        # 在排序前进行时长切分
        # 这会将 30s 的 Intro 切分为 3 个 10s 的片段，每个都会进行独立的视频搜索
        segments = self._split_by_duration(segments, max_duration=12.0)
        
        # 按开始时间排序，确保时间线连续性
        segments.sort(key=lambda x: float(x.get("start", 0)))

        timeline = TimelineResult()
        cursor_ms = 0
        total_segments = len(segments)

        for seg_idx, seg in enumerate(segments):
            # 更新进度: 30% - 95% 对应视频匹配阶段
            if total_segments > 0:
                match_progress = 30.0 + (seg_idx / total_segments) * 65.0
                await report_progress(match_progress)
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

            # 🎵 间隙处理策略 (Gap Handling Strategy)
            # 目标：确保视频时间线连续，无黑屏，无跳跃
            if cursor_ms > 0:  # 只有非第一句才需要处理间隙（第一句前面是0）
                if start_ms > cursor_ms:
                    gap = start_ms - cursor_ms
                    
                    # 策略 1: 大间隙 -> 插入间奏片段
                    if gap > 2000:
                        self._logger.info(
                            "timeline_builder.fill_large_gap",
                            gap_start=cursor_ms,
                            gap_end=start_ms,
                            duration=gap,
                            message="发现大间隙，插入纯音乐画面",
                        )
                        
                        # 搜索纯音乐画面
                        gap_prompt = "atmospheric music video, cinematic scenes, instrumental, no lyrics"
                        gap_candidates = await self._get_candidates(gap_prompt, limit=20)
                        normalized_gap = self._normalize_candidates(gap_candidates, cursor_ms, start_ms)
                        selected_gap = self._select_diverse_candidates(normalized_gap, limit=3)
                        
                        # 兜底
                        if not selected_gap:
                            selected_gap = [{
                                "id": str(uuid4()),
                                "source_video_id": self._settings.fallback_video_id,
                                "start_time_ms": cursor_ms,
                                "end_time_ms": start_ms,
                                "score": 0.0,
                            }]

                        # 标记已使用
                        for candidate in selected_gap:
                            segment_key = (
                                str(candidate.get("source_video_id")),
                                int(candidate.get("start_time_ms", 0)),
                                int(candidate.get("end_time_ms", 0)),
                            )
                            self._used_segments[segment_key] = self._used_segments.get(segment_key, 0) + 1

                        timeline.lines.append(
                            TimelineLine(
                                text="(Instrumental)",
                                start_ms=cursor_ms,
                                end_ms=start_ms,
                                candidates=selected_gap
                            )
                        )
                    
                    # 策略 2: 小间隙 -> 吸收（向前延伸当前片段）
                    else:
                        self._logger.info(
                            "timeline_builder.absorb_small_gap",
                            original_start=start_ms,
                            new_start=cursor_ms,
                            gap_absorbed=gap,
                            message="吸收微小间隙，向前延伸当前片段",
                        )
                        start_ms = cursor_ms  # 修改当前片段的开始时间

            # 处理当前片段
            if seg.get("is_non_lyric", False):
                # 短 Credit -> Fallback
                candidates = []
            else:
                # 优先使用 search_prompt (针对 Long Credit/Intro)
                search_query = seg.get("search_prompt", text)
                candidates = await self._get_candidates(search_query, limit=20)

            normalized = self._normalize_candidates(candidates, start_ms, end_ms)

            # 选择未使用或使用次数最少的片段
            selected_candidates = self._select_diverse_candidates(normalized, limit=3)

            # 标记所有候选片段为已使用（防止后续句子重复使用）
            for candidate in selected_candidates:
                segment_key = (
                    str(candidate.get("source_video_id")),
                    int(candidate.get("start_time_ms", 0)),
                    int(candidate.get("end_time_ms", 0)),
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
            cursor_ms = max(cursor_ms, end_ms)
            
        # 🎵 尾部填充逻辑 (Tail Gap Filling)
        self._logger.info(
            "timeline_builder.check_tail_gap",
            audio_duration_ms=audio_duration_ms,
            cursor_ms=cursor_ms,
            gap=audio_duration_ms - cursor_ms,
            threshold=1000,
            should_fill=audio_duration_ms > cursor_ms + 1000
        )
        
        if audio_duration_ms > cursor_ms + 1000:
            gap_start = cursor_ms
            gap_end = audio_duration_ms
            self._logger.info(
                "timeline_builder.fill_tail_gap",
                gap_start=gap_start,
                gap_end=gap_end,
                duration=gap_end - gap_start,
                message="填充尾部空隙",
            )
            
            outro_prompt = "ending music video, fade out, cinematic, atmospheric"
            outro_candidates = await self._get_candidates(outro_prompt, limit=20)
            normalized_outro = self._normalize_candidates(outro_candidates, gap_start, gap_end)
            selected_outro = self._select_diverse_candidates(normalized_outro, limit=3)
            
            # 如果因为重叠等原因没有选到候选，强制使用 fallback
            if not selected_outro:
                self._logger.warning(
                    "timeline_builder.outro_fallback",
                    gap_start=gap_start,
                    gap_end=gap_end,
                    message="Outro 搜索无可用候选，使用 Fallback",
                )
                selected_outro = [{
                    "id": str(uuid4()),
                    "source_video_id": self._settings.fallback_video_id,
                    "start_time_ms": gap_start,
                    "end_time_ms": gap_end,
                    "score": 0.0,
                }]

            timeline.lines.append(
                TimelineLine(
                    text="(Outro)",
                    start_ms=gap_start,
                    end_ms=gap_end,
                    candidates=selected_outro
                )
            )

        await report_progress(100.0)  # 100%: 时间线生成完成
        return timeline

    def _normalize_candidates(
        self, raw_candidates: list[dict[str, int | float | str]], start_ms: int, end_ms: int
    ) -> list[dict[str, int | float | str]]:
        """
        规范化候选视频片段，过滤掉时长严重不匹配的候选。

        过滤策略：
        - 如果 API 返回的视频片段时长与歌词时长相差超过阈值，则跳过该候选
        - 阈值：歌词时长 ≥ 5秒 且 视频时长 < 歌词时长 50% 时过滤
        - 例如：歌词 30 秒，但视频只有 5 秒 → 过滤掉
        """
        lyric_duration_ms = end_ms - start_ms
        lyric_duration_s = lyric_duration_ms / 1000.0

        def _candidate_defaults(candidate: dict[str, int | float | str]) -> dict[str, int | float | str] | None:
            # 🔧 修复: 从 API 返回片段的中间位置截取，以获得最匹配的画面
            # 原因：AI 匹配的精彩画面往往在片段中间，而不是开头
            api_start = int(candidate.get("start", start_ms))
            api_end = int(candidate.get("end", end_ms))
            lyric_duration = end_ms - start_ms

            # 检查视频片段时长是否足够
            api_duration_ms = api_end - api_start
            api_duration_s = api_duration_ms / 1000.0

            # 过滤策略：如果歌词时长 ≥ 5秒 且 视频时长 < 歌词时长的 50%，则过滤掉
            if lyric_duration_s >= 5.0 and api_duration_ms < lyric_duration_ms * 0.5:
                self._logger.warning(
                    "timeline_builder.duration_mismatch",
                    video_id=candidate.get("video_id"),
                    lyric_duration_s=round(lyric_duration_s, 2),
                    api_duration_s=round(api_duration_s, 2),
                    shortage_s=round(lyric_duration_s - api_duration_s, 2),
                    shortage_pct=round((1 - api_duration_s / lyric_duration_s) * 100, 1),
                    message="视频片段时长严重不足，跳过该候选",
                )
                return None

            # 计算API片段的中间位置
            api_duration = api_end - api_start
            api_middle = api_start + (api_duration // 2)

            # 从中间位置向前偏移一半歌词时长，使歌词时长居中
            clip_start = api_middle - (lyric_duration // 2)
            clip_end = clip_start + lyric_duration

            # 🔧 修复：允许超出API片段边界，由 video_fetcher 自动处理循环/裁剪
            #
            # 原问题：当API返回的片段短于歌词时长时，边界检查会将选择截断到API长度
            # 例如：歌词需要8s，API只有5s，原逻辑会将选择截断为5s，导致时长不足
            #
            # 新逻辑：保持完整的歌词时长需求，让 video_fetcher 处理边界情况
            # - 如果超出视频末尾，video_fetcher 会自动使用循环模式 (_cut_clip_with_loop)
            # - 如果起始位置为负，调整到从视频开头开始
            if clip_start < api_start:
                # 起始位置提前：从API开头开始，保持歌词时长
                clip_start = api_start
                clip_end = clip_start + lyric_duration
                # 不再限制 clip_end，允许超出 api_end
            # 不处理 clip_end > api_end 的情况，让它自然超出
            # video_fetcher 会检测到并使用循环模式

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
                "api_duration_ms": api_duration_ms,
                "lyric_start_ms": start_ms,
                "lyric_end_ms": end_ms,
                "lyric_duration_ms": lyric_duration_ms,
            }

        if raw_candidates:
            # 处理所有候选，过滤掉 None（时长不匹配的）
            normalized = []
            for c in raw_candidates:
                result = _candidate_defaults(c)
                if result is not None:
                    normalized.append(result)

            # 如果所有候选都被过滤掉了，返回 fallback
            if not normalized:
                self._logger.warning(
                    "timeline_builder.all_candidates_filtered",
                    lyric_duration_s=round(lyric_duration_s, 2),
                    original_count=len(raw_candidates),
                    message="所有候选视频时长都不匹配，使用 fallback 视频",
                )
                return [
                    {
                        "id": str(uuid4()),
                        "source_video_id": self._settings.fallback_video_id,
                        "start_time_ms": start_ms,
                        "end_time_ms": end_ms,
                        "score": 0.0,
                    }
                ]

            return normalized

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
        从候选列表中选择多样化的片段，严格确保每个片段只使用一次。

        **严格策略**（按用户要求）：
        1. 完全禁止重复使用：usage_count > 0 的片段直接剔除
        2. 完全禁止重叠：任何重叠 > 0 的片段直接剔除
        3. 如果没有可用片段，返回空（使用 fallback 视频）
        4. 按评分降序排序选择最佳的未使用片段
        """
        if not candidates:
            return []

        # 为每个候选片段检测使用次数和时间重叠
        valid_candidates: list[CandidateWithUsage] = []
        rejected_count = 0

        for candidate in candidates:
            video_id = str(candidate.get("source_video_id", ""))
            start_ms = int(candidate.get("start_time_ms", 0))
            end_ms = int(candidate.get("end_time_ms", 0))
            segment_key = (video_id, start_ms, end_ms)

            # 策略1：完全禁止重复使用 - 检查精确匹配
            usage_count = self._used_segments.get(segment_key, 0)
            if usage_count > 0:
                self._logger.info(
                    "timeline_builder.reject_reused",
                    video_id=video_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    usage_count=usage_count,
                    message="严格去重：片段已使用过，直接剔除",
                )
                rejected_count += 1
                continue

            # 策略2：完全禁止重叠 - 检查与所有已使用片段的重叠
            has_overlap = False
            for used_key in self._used_segments.keys():
                used_video_id, used_start, used_end = used_key
                if used_video_id == video_id:
                    overlap_ratio = calculate_overlap_ratio(start_ms, end_ms, used_start, used_end)
                    if overlap_ratio > 0:
                        has_overlap = True
                        self._logger.info(
                            "timeline_builder.reject_overlap",
                            video_id=video_id,
                            start_ms=start_ms,
                            end_ms=end_ms,
                            overlapping_with=used_key,
                            overlap_ratio=round(overlap_ratio, 3),
                            message="严格去重：片段与已使用片段重叠，直接剔除",
                        )
                        rejected_count += 1
                        break

            if has_overlap:
                continue

            # 通过所有检查，加入有效候选列表
            valid_candidates.append({
                "candidate": candidate,
                "usage_count": 0,  # 肯定是 0，因为已经过滤掉了 > 0 的
                "score": float(candidate.get("score", 0.0)),
            })

        # 策略4：按评分降序排序选择最佳的
        valid_candidates.sort(key=lambda x: -x["score"])

        # 提取候选片段并限制数量
        selected: list[dict[str, int | float | str]] = [
            item["candidate"] for item in valid_candidates[:limit]
        ]

        # 策略3：如果没有可用片段，返回空（触发 fallback）
        if not selected:
            self._logger.warning(
                "timeline_builder.no_valid_candidates",
                total_candidates=len(candidates),
                rejected_count=rejected_count,
                message="严格去重：所有候选都已使用或重叠，将使用 fallback 视频",
            )
            return []

        # 记录选中的片段详细信息
        for idx, item in enumerate(valid_candidates[:limit]):
            candidate = item["candidate"]
            self._logger.info(
                "timeline_builder.selected_clip",
                index=idx + 1,
                video_id=candidate.get("source_video_id"),
                start_ms=candidate.get("start_time_ms"),
                end_ms=candidate.get("end_time_ms"),
                duration_ms=candidate.get("end_time_ms", 0) - candidate.get("start_time_ms", 0),
                score=candidate.get("score"),
                message="严格去重通过：未使用且无重叠",
            )

        self._logger.info(
            "timeline_builder.strict_deduplication_summary",
            total_candidates=len(candidates),
            valid_count=len(valid_candidates),
            rejected_count=rejected_count,
            selected_count=len(selected),
            message=f"严格去重：从{len(candidates)}个候选中筛选出{len(valid_candidates)}个有效，选择了{len(selected)}个",
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

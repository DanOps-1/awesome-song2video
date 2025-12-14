"""构建歌词与视频片段的时间线。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, TypedDict
from uuid import uuid4

import structlog

from src.infra.config.settings import get_settings
from src.pipelines.lyrics_ingest.transcriber import transcribe_with_timestamps
from src.services.matching.query_rewriter import QueryRewriter
from src.services.matching.twelvelabs_client import client
from src.audio.beat_detector import BeatAnalysisResult, find_nearest_beat
from src.audio.onset_detector import OnsetResult
from src.services.matching.action_detector import action_detector
from src.services.matching.beat_aligner import beat_aligner
from src.services.matching.twelvelabs_video_fetcher import video_fetcher

# 进度回调类型: async def callback(progress: float) -> None
ProgressCallback = Callable[[float], Coroutine[Any, Any, None]]


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
        # 缓存所有曾经见过的候选片段，用于随机选择
        self._all_seen_candidates: list[dict[str, Any]] = []
        # 卡点相关配置
        self._beat_align_max_offset_ms = 200  # 画面切换最多提前/延后 200ms 对齐节拍

        # 画面连贯性：追踪上一个使用的视频，优先选择同源片段
        self._last_used_video_id: str | None = None
        self._continuity_bonus = 0.15  # 同源视频的评分加成

        # 通用搜索查询词列表，用于获取多样化的素材
        self._generic_queries = [
            "action scene",
            "character running",
            "chase scene",
            "funny moment",
            "cartoon animation",
            "character interaction",
            "dramatic scene",
            "comedy scene",
        ]
        self._generic_query_index = 0

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
            r"^作词[\s:：]",
            r"^词[\s:：]",
            r"^作曲[\s:：]",
            r"^曲[\s:：]",
            r"^编曲[\s:：]",
            r"^编[\s:：]",
            r"^演唱[\s:：]",
            r"^唱[\s:：]",
            r"^制作[\s:：]",
            r"^监制[\s:：]",
            r"^混音[\s:：]",
            r"^母带[\s:：]",
        ]

        # 英文 credits 模式
        english_patterns = [
            r"(?i)^lyrics\s+by",
            r"(?i)^music\s+by",
            r"(?i)^composed\s+by",
            r"(?i)^arranged\s+by",
            r"(?i)^performed\s+by",
            r"(?i)^produced\s+by",
        ]

        all_patterns = non_lyric_patterns + english_patterns

        for pattern in all_patterns:
            if re.search(pattern, text):
                return True

        return False

    def _align_start_to_beat(
        self,
        start_ms: int,
        end_ms: int,
        beats: BeatAnalysisResult | None,
        prev_end_ms: int = 0,
    ) -> tuple[int, int]:
        """将画面切换点（start_ms）对齐到最近的节拍。

        简化版卡点：让每次画面切换都落在音乐节拍上，
        视觉效果会更有节奏感。

        Args:
            start_ms: 原始开始时间
            end_ms: 原始结束时间
            beats: 节拍分析结果
            prev_end_ms: 上一个片段的结束时间（防止重叠）

        Returns:
            (aligned_start_ms, aligned_end_ms) 对齐后的时间
        """
        if not beats or not self._settings.beat_sync_enabled:
            return start_ms, end_ms

        # 找最近的节拍
        result = find_nearest_beat(
            beats, start_ms, max_offset_ms=self._beat_align_max_offset_ms
        )

        if result is None:
            return start_ms, end_ms

        nearest_beat_ms, offset_ms = result

        # 确保不与上一个片段重叠
        if nearest_beat_ms < prev_end_ms:
            return start_ms, end_ms

        # 保持时长不变，只调整起止时间
        duration = end_ms - start_ms
        aligned_start = nearest_beat_ms
        aligned_end = aligned_start + duration

        if offset_ms != 0:
            self._logger.debug(
                "timeline_builder.beat_aligned",
                original_start=start_ms,
                aligned_start=aligned_start,
                offset_ms=offset_ms,
                nearest_beat=nearest_beat_ms,
            )

        return aligned_start, aligned_end

    def _get_audio_duration(self, audio_path: Path) -> int:
        """使用 ffprobe 获取音频文件时长（毫秒）。"""
        import subprocess

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
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

    def _split_by_duration(
        self, segments: list[dict[str, Any]], max_duration: float = 12.0
    ) -> list[dict[str, Any]]:
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
                    new_seg["search_prompt"] = f"{base_prompt}, scene {i + 1}"

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
            "timeline_builder.audio_info", path=str(audio_path), duration_ms=audio_duration_ms
        )
        await report_progress(20.0)  # 20%: 开始 Whisper 识别

        raw_segments = await transcribe_with_timestamps(
            audio_path, language=language, prompt=prompt
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
        beats: BeatAnalysisResult | None = None,
        music_onsets: OnsetResult | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> TimelineResult:
        """对已确认的歌词行进行视频匹配。

        Args:
            lines: 歌词行列表，格式 [{"text": "...", "start_ms": int, "end_ms": int}, ...]
            audio_duration_ms: 音频总时长（毫秒），用于填充尾部
            beats: 音频节拍分析结果（用于 action 模式卡点）
            music_onsets: 音乐鼓点检测结果（用于 onset 模式卡点，类似剪映）
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
            segments.append(
                {
                    "text": line["text"],
                    "start": line["start_ms"] / 1000.0,
                    "end": line["end_ms"] / 1000.0,
                }
            )

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

            # 🎵 简化版卡点：将画面切换点对齐到最近的节拍
            if beats and self._settings.beat_sync_enabled:
                aligned_start, aligned_end = self._align_start_to_beat(
                    start_ms, end_ms, beats, prev_end_ms=cursor_ms
                )
                if aligned_start != start_ms:
                    self._logger.info(
                        "timeline_builder.cut_aligned_to_beat",
                        text=text[:20],
                        original_start=start_ms,
                        aligned_start=aligned_start,
                        offset_ms=aligned_start - start_ms,
                    )
                    start_ms = aligned_start
                    end_ms = aligned_end

            # 间隙处理
            if cursor_ms > 0 and start_ms > cursor_ms:
                gap = start_ms - cursor_ms
                if gap > 2000:
                    gap_prompt = (
                        "atmospheric music video, cinematic scenes, instrumental, no lyrics"
                    )
                    gap_candidates = await self._get_candidates(gap_prompt, limit=20)
                    normalized_gap = self._normalize_candidates(gap_candidates, cursor_ms, start_ms)
                    selected_gap = self._select_diverse_candidates(normalized_gap, limit=5)
                    if not selected_gap:
                        # 随机选择一个未使用的片段
                        gap_duration = start_ms - cursor_ms
                        random_gap = await self._get_random_unused_segment(
                            gap_duration, cursor_ms, start_ms
                        )
                        if random_gap:
                            selected_gap = [random_gap]
                    for candidate in selected_gap:
                        segment_key = (
                            str(candidate.get("source_video_id")),
                            int(candidate.get("start_time_ms", 0)),
                            int(candidate.get("end_time_ms", 0)),
                        )
                        self._used_segments[segment_key] = (
                            self._used_segments.get(segment_key, 0) + 1
                        )
                    timeline.lines.append(
                        TimelineLine(
                            text="(Instrumental)",
                            start_ms=cursor_ms,
                            end_ms=start_ms,
                            candidates=selected_gap,
                        )
                    )
                else:
                    start_ms = cursor_ms

            # 处理当前片段
            if seg.get("is_non_lyric", False):
                candidates = []
            else:
                search_query = seg.get("search_prompt", text)
                candidates = await self._get_candidates(search_query, limit=20)

            normalized = self._normalize_candidates(candidates, start_ms, end_ms)

            # 应用卡点评分
            # 注意：onset 模式的鼓点分析移到渲染阶段，避免匹配时分析多个候选导致太慢
            beat_sync_mode = self._settings.beat_sync_mode if self._settings.beat_sync_enabled else None

            if beat_sync_mode == "action" and beats and beat_aligner.should_apply_beat_sync(beats):
                # 动作高光对齐模式（旧模式，在匹配阶段计算）
                selected_candidates = await self._select_candidates_with_beat_sync(
                    normalized, limit=5, lyric_start_ms=start_ms, beats=beats
                )
            else:
                # onset 模式或无卡点：只按 TwelveLabs 评分选择，鼓点分析在渲染时实时进行
                selected_candidates = self._select_diverse_candidates(normalized, limit=5)

            # 如果所有候选都被去重拒绝，随机选择一个未使用的片段
            if not selected_candidates:
                lyric_duration_ms = end_ms - start_ms
                random_segment = await self._get_random_unused_segment(
                    lyric_duration_ms, start_ms, end_ms
                )
                if random_segment:
                    selected_candidates = [random_segment]

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

        # 尾部填充
        if audio_duration_ms > cursor_ms + 1000:
            gap_start = cursor_ms
            gap_end = audio_duration_ms
            outro_prompt = "ending music video, fade out, cinematic, atmospheric"
            outro_candidates = await self._get_candidates(outro_prompt, limit=20)
            normalized_outro = self._normalize_candidates(outro_candidates, gap_start, gap_end)
            selected_outro = self._select_diverse_candidates(normalized_outro, limit=5)
            if not selected_outro:
                # 随机选择一个未使用的片段
                outro_duration = gap_end - gap_start
                random_outro = await self._get_random_unused_segment(
                    outro_duration, gap_start, gap_end
                )
                if random_outro:
                    selected_outro = [random_outro]
            timeline.lines.append(
                TimelineLine(
                    text="(Outro)", start_ms=gap_start, end_ms=gap_end, candidates=selected_outro
                )
            )

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
                "timeline_builder.audio_info", path=str(audio_path), duration_ms=audio_duration_ms
            )
            await report_progress(10.0)  # 10%: 开始 Whisper 识别
            raw_segments = await transcribe_with_timestamps(
                audio_path, language=language, prompt=prompt
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
                        gap_prompt = (
                            "atmospheric music video, cinematic scenes, instrumental, no lyrics"
                        )
                        gap_candidates = await self._get_candidates(gap_prompt, limit=20)
                        normalized_gap = self._normalize_candidates(
                            gap_candidates, cursor_ms, start_ms
                        )
                        selected_gap = self._select_diverse_candidates(normalized_gap, limit=5)

                        # 兜底：随机选择未使用的片段
                        if not selected_gap:
                            gap_duration = start_ms - cursor_ms
                            random_gap = await self._get_random_unused_segment(
                                gap_duration, cursor_ms, start_ms
                            )
                            if random_gap:
                                selected_gap = [random_gap]

                        # 标记已使用
                        for candidate in selected_gap:
                            segment_key = (
                                str(candidate.get("source_video_id")),
                                int(candidate.get("start_time_ms", 0)),
                                int(candidate.get("end_time_ms", 0)),
                            )
                            self._used_segments[segment_key] = (
                                self._used_segments.get(segment_key, 0) + 1
                            )

                        timeline.lines.append(
                            TimelineLine(
                                text="(Instrumental)",
                                start_ms=cursor_ms,
                                end_ms=start_ms,
                                candidates=selected_gap,
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
            selected_candidates = self._select_diverse_candidates(normalized, limit=5)

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
            should_fill=audio_duration_ms > cursor_ms + 1000,
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
            selected_outro = self._select_diverse_candidates(normalized_outro, limit=5)

            # 如果因为重叠等原因没有选到候选，强制使用 fallback
            if not selected_outro:
                # 随机选择一个未使用的片段
                outro_duration = gap_end - gap_start
                random_segment = await self._get_random_unused_segment(
                    outro_duration, gap_start, gap_end
                )
                if random_segment:
                    selected_outro = [random_segment]
                else:
                    self._logger.warning(
                        "timeline_builder.outro_no_segment",
                        gap_start=gap_start,
                        gap_end=gap_end,
                        message="Outro 无法找到未使用的片段，跳过",
                    )

            timeline.lines.append(
                TimelineLine(
                    text="(Outro)", start_ms=gap_start, end_ms=gap_end, candidates=selected_outro
                )
            )

        await report_progress(100.0)  # 100%: 时间线生成完成
        return timeline

    def _normalize_candidates(
        self, raw_candidates: list[dict[str, int | float | str]], start_ms: int, end_ms: int
    ) -> list[dict[str, int | float | str]]:
        """
        规范化候选视频片段，过滤掉时长不足的候选。

        过滤策略：
        - 视频片段时长必须 >= 歌词时长，否则丢弃
        - 禁止循环播放，确保画面连贯性
        """
        lyric_duration_ms = end_ms - start_ms
        lyric_duration_s = lyric_duration_ms / 1000.0

        def _candidate_defaults(
            candidate: dict[str, int | float | str],
        ) -> dict[str, int | float | str] | None:
            api_start = int(candidate.get("start", start_ms))
            api_end = int(candidate.get("end", end_ms))
            lyric_duration = end_ms - start_ms

            # 检查视频片段时长是否足够
            api_duration_ms = api_end - api_start
            api_duration_s = api_duration_ms / 1000.0

            # 严格过滤：视频时长必须 >= 歌词时长，否则丢弃
            if api_duration_ms < lyric_duration_ms:
                self._logger.debug(
                    "timeline_builder.duration_insufficient",
                    video_id=candidate.get("video_id"),
                    lyric_duration_s=round(lyric_duration_s, 2),
                    api_duration_s=round(api_duration_s, 2),
                    shortage_s=round(lyric_duration_s - api_duration_s, 2),
                    message="视频时长不足，丢弃该候选",
                )
                return None

            # 从 API 返回片段的中间位置截取，以获得最匹配的画面
            api_duration = api_end - api_start
            api_middle = api_start + (api_duration // 2)

            # 从中间位置向前偏移一半歌词时长，使歌词时长居中
            clip_start = api_middle - (lyric_duration // 2)
            clip_end = clip_start + lyric_duration

            # 边界检查：确保不超出 API 片段范围
            if clip_start < api_start:
                clip_start = api_start
                clip_end = clip_start + lyric_duration

            if clip_end > api_end:
                clip_end = api_end
                clip_start = clip_end - lyric_duration

            return {
                "id": str(uuid4()),
                "source_video_id": candidate["video_id"],  # 必须有 video_id
                "start_time_ms": clip_start,
                "end_time_ms": clip_end,
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

            # 如果所有候选都被过滤掉了，返回空列表，让调用方使用随机选择
            if not normalized:
                self._logger.warning(
                    "timeline_builder.all_candidates_filtered",
                    lyric_duration_s=round(lyric_duration_s, 2),
                    original_count=len(raw_candidates),
                    message="所有候选视频时长都不匹配，返回空列表待随机选择",
                )
                return []

            return normalized

        # 没有原始候选时返回空列表，让调用方决定如何处理
        return []

    async def _get_random_unused_segment(
        self, lyric_duration_ms: int, start_ms: int, end_ms: int
    ) -> dict[str, Any] | None:
        """
        当所有候选都被去重拒绝时，使用通用查询搜索未使用的片段。

        策略：
        1. 先从已缓存的候选中查找未使用的片段
        2. 如果没有，使用通用查询词搜索新的片段
        3. 筛选出未使用且不重叠的片段
        4. 随机选择一个返回
        """
        import random

        def is_segment_available(video_id: str, seg_start: int, seg_end: int) -> bool:
            """检查片段是否可用（未使用且不与已使用片段重叠）"""
            segment_key = (video_id, seg_start, seg_end)

            # 检查精确匹配
            if self._used_segments.get(segment_key, 0) > 0:
                return False

            # 检查重叠
            for used_key in self._used_segments.keys():
                used_video_id, used_start, used_end = used_key
                if used_video_id == video_id:
                    overlap = calculate_overlap_ratio(seg_start, seg_end, used_start, used_end)
                    if overlap > 0:
                        return False

            return True

        def try_extract_segment(candidate: dict[str, Any]) -> dict[str, Any] | None:
            """尝试从候选中提取可用片段"""
            video_id = candidate.get("video_id", "")
            # TwelveLabs 客户端返回的 start/end 已经是毫秒
            api_start = int(candidate.get("start", 0))
            api_end = int(candidate.get("end", 0))
            api_duration_ms = api_end - api_start

            # 检查时长是否足够
            if api_duration_ms < lyric_duration_ms:
                return None

            # 计算裁剪位置（从中间截取）
            api_duration = api_end - api_start
            api_middle = api_start + (api_duration // 2)
            clip_start = api_middle - (lyric_duration_ms // 2)
            clip_end = clip_start + lyric_duration_ms

            # 边界检查
            if clip_start < api_start:
                clip_start = api_start
                clip_end = clip_start + lyric_duration_ms
            if clip_end > api_end:
                clip_end = api_end
                clip_start = clip_end - lyric_duration_ms

            # 检查是否可用
            if not is_segment_available(video_id, clip_start, clip_end):
                return None

            return {
                "id": str(uuid4()),
                "source_video_id": video_id,
                "start_time_ms": clip_start,
                "end_time_ms": clip_end,
                "score": candidate.get("score", 0.0),
                "is_random_fill": True,
                "lyric_start_ms": start_ms,
                "lyric_end_ms": end_ms,
            }

        # 策略1：从已缓存的候选中查找
        available_from_cache = []
        for candidate in self._all_seen_candidates:
            result = try_extract_segment(candidate)
            if result:
                available_from_cache.append(result)

        if available_from_cache:
            selected = random.choice(available_from_cache)
            self._logger.info(
                "timeline_builder.random_fill_from_cache",
                video_id=selected["source_video_id"],
                start_ms=selected["start_time_ms"],
                end_ms=selected["end_time_ms"],
                cache_available=len(available_from_cache),
                message="从缓存中随机选择未使用片段",
            )
            return selected

        # 策略2：使用通用查询搜索新的片段
        query = self._generic_queries[self._generic_query_index % len(self._generic_queries)]
        self._generic_query_index += 1

        self._logger.info(
            "timeline_builder.random_fill_search",
            query=query,
            message="使用通用查询搜索新片段",
        )

        new_candidates = await client.search_segments(query, limit=50)

        # 将新候选加入缓存
        for c in new_candidates:
            if c not in self._all_seen_candidates:
                self._all_seen_candidates.append(c)

        # 从新候选中查找可用片段
        available_from_search = []
        for candidate in new_candidates:
            result = try_extract_segment(candidate)
            if result:
                available_from_search.append(result)

        if available_from_search:
            selected = random.choice(available_from_search)
            self._logger.info(
                "timeline_builder.random_fill_from_search",
                video_id=selected["source_video_id"],
                start_ms=selected["start_time_ms"],
                end_ms=selected["end_time_ms"],
                search_available=len(available_from_search),
                message="从通用搜索中随机选择未使用片段",
            )
            return selected

        # 如果还是没有，记录警告并返回 None
        self._logger.warning(
            "timeline_builder.no_available_segments",
            lyric_duration_ms=lyric_duration_ms,
            used_count=len(self._used_segments),
            cache_size=len(self._all_seen_candidates),
            message="无法找到任何可用的未使用片段",
        )
        return None

    async def _get_candidates(self, text: str, limit: int) -> list[dict[str, Any]]:
        """
        获取候选片段，基于分数阈值的智能改写策略：

        1. 原始查询 → 获取结果和 top score
        2. score >= threshold (0.9) → 直接使用原始结果（直白歌词）
        3. score < threshold → 尝试改写 → 对比选择更好的结果（抽象歌词）
        4. 改写后分数更高 → 使用改写结果
        5. 改写后分数更低 → 使用原始结果
        """
        key = (text, limit)
        if key not in self._candidate_cache:
            candidates: list[dict[str, Any]] = []
            score_threshold = self._settings.query_rewrite_score_threshold

            # 第一步：用原始歌词搜索
            original_candidates = await client.search_segments(text, limit=limit)
            original_top_score = (
                float(original_candidates[0].get("score", 0.0))
                if original_candidates
                else 0.0
            )

            self._logger.info(
                "timeline_builder.original_search",
                query=text[:50],
                count=len(original_candidates),
                top_score=round(original_top_score, 3),
                threshold=score_threshold,
            )

            # 第二步：根据分数决定是否改写
            if original_top_score >= score_threshold:
                # 分数足够高，直接使用原始结果（直白歌词，不需要改写）
                candidates = original_candidates
                self._logger.info(
                    "timeline_builder.skip_rewrite",
                    query=text[:30],
                    score=round(original_top_score, 3),
                    reason="score >= threshold, no rewrite needed",
                )
            elif self._rewriter._enabled:
                # 分数低于阈值，使用 DeepSeek 改写一次
                rewritten_query = await self._rewriter.rewrite(text)

                # 如果改写结果与原始相同，使用原始结果
                if rewritten_query == text:
                    self._logger.debug(
                        "timeline_builder.rewrite_identical",
                        original=text[:30],
                    )
                    candidates = original_candidates
                else:
                    # 用改写后的查询搜索
                    rewritten_candidates = await client.search_segments(
                        rewritten_query, limit=limit
                    )
                    rewritten_top_score = (
                        float(rewritten_candidates[0].get("score", 0.0))
                        if rewritten_candidates
                        else 0.0
                    )

                    self._logger.info(
                        "timeline_builder.rewrite_search",
                        original=text[:30],
                        rewritten=rewritten_query[:50],
                        original_score=round(original_top_score, 3),
                        rewritten_score=round(rewritten_top_score, 3),
                    )

                    # 选择更好的结果
                    if rewritten_top_score > original_top_score:
                        candidates = rewritten_candidates
                        self._logger.info(
                            "timeline_builder.rewrite_better",
                            original=text[:30],
                            rewritten=rewritten_query[:50],
                            score_improvement=round(rewritten_top_score - original_top_score, 3),
                        )
                    else:
                        candidates = original_candidates
                        self._logger.info(
                            "timeline_builder.rewrite_not_better",
                            original=text[:30],
                            rewritten=rewritten_query[:50],
                            reason="original score was better",
                        )

            else:
                # 改写未启用，使用原始结果
                candidates = original_candidates

            self._candidate_cache[key] = candidates

            # 将新候选加入全局缓存，用于随机选择
            for c in candidates:
                if c not in self._all_seen_candidates:
                    self._all_seen_candidates.append(c)

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
            # 🎬 画面连贯性：同源视频加分
            original_score = float(candidate.get("score", 0.0))
            continuity_bonus = 0.0
            if self._last_used_video_id and video_id == self._last_used_video_id:
                continuity_bonus = self._continuity_bonus
            adjusted_score = original_score + continuity_bonus

            valid_candidates.append(
                {
                    "candidate": candidate,
                    "usage_count": 0,  # 肯定是 0，因为已经过滤掉了 > 0 的
                    "score": adjusted_score,
                    "original_score": original_score,
                    "continuity_bonus": continuity_bonus,
                    "video_id": video_id,
                }
            )

        # 策略4：按评分降序排序选择最佳的（包含连贯性加成）
        valid_candidates.sort(key=lambda x: -x["score"])

        # 提取候选片段并限制数量
        selected: list[dict[str, int | float | str]] = [
            item["candidate"] for item in valid_candidates[:limit]
        ]

        # 策略3：如果没有可用片段，返回空列表，让调用方使用随机选择
        if not selected:
            self._logger.warning(
                "timeline_builder.no_valid_candidates",
                total_candidates=len(candidates),
                rejected_count=rejected_count,
                message="严格去重：所有候选都已使用或重叠，将随机选择未使用片段",
            )
            return []

        # 记录选中的片段详细信息
        for idx, item in enumerate(valid_candidates[:limit]):
            candidate = item["candidate"]
            continuity_info = ""
            if item.get("continuity_bonus", 0) > 0:
                continuity_info = f" [连贯性加成 +{item['continuity_bonus']:.2f}]"
            self._logger.info(
                "timeline_builder.selected_clip",
                index=idx + 1,
                video_id=item.get("video_id"),
                start_ms=candidate.get("start_time_ms"),
                end_ms=candidate.get("end_time_ms"),
                duration_ms=candidate.get("end_time_ms", 0) - candidate.get("start_time_ms", 0),
                original_score=item.get("original_score"),
                adjusted_score=item.get("score"),
                continuity_bonus=item.get("continuity_bonus", 0),
                message=f"选中片段{continuity_info}",
            )

        # 🎬 更新最后使用的视频ID（用于连贯性评分）
        if valid_candidates:
            self._last_used_video_id = valid_candidates[0].get("video_id")
            self._logger.debug(
                "timeline_builder.continuity_tracking",
                last_video_id=self._last_used_video_id,
            )

        self._logger.info(
            "timeline_builder.strict_deduplication_summary",
            total_candidates=len(candidates),
            valid_count=len(valid_candidates),
            rejected_count=rejected_count,
            selected_count=len(selected),
            last_video_id=self._last_used_video_id,
            message=f"严格去重：从{len(candidates)}个候选中筛选出{len(valid_candidates)}个有效，选择了{len(selected)}个",
        )

        return selected

    async def _select_candidates_with_beat_sync(
        self,
        candidates: list[dict[str, int | float | str]],
        limit: int,
        lyric_start_ms: int,
        beats: BeatAnalysisResult,
    ) -> list[dict[str, int | float | str]]:
        """
        选择候选片段并应用卡点评分。

        流程:
        1. 先用严格去重筛选有效候选
        2. 获取每个候选视频的动作档案
        3. 计算卡点对齐分数
        4. 按综合评分排序选择
        5. 存储 beat_sync_offset_ms 供渲染使用

        Args:
            candidates: 候选片段列表
            limit: 选择数量限制
            lyric_start_ms: 歌词行起始时间
            beats: 节拍分析结果

        Returns:
            带有 beat_sync_offset_ms 的候选列表
        """
        if not candidates:
            return []

        # 第一步：应用严格去重过滤
        valid_candidates: list[dict[str, Any]] = []
        rejected_count = 0

        for candidate in candidates:
            video_id = str(candidate.get("source_video_id", ""))
            start_ms = int(candidate.get("start_time_ms", 0))
            end_ms = int(candidate.get("end_time_ms", 0))
            segment_key = (video_id, start_ms, end_ms)

            # 检查精确匹配重复
            usage_count = self._used_segments.get(segment_key, 0)
            if usage_count > 0:
                rejected_count += 1
                continue

            # 检查时间重叠
            has_overlap = False
            for used_key in self._used_segments.keys():
                used_video_id, used_start, used_end = used_key
                if used_video_id == video_id:
                    overlap_ratio = calculate_overlap_ratio(start_ms, end_ms, used_start, used_end)
                    if overlap_ratio > 0:
                        has_overlap = True
                        rejected_count += 1
                        break

            if has_overlap:
                continue

            valid_candidates.append(dict(candidate))

        if not valid_candidates:
            self._logger.warning(
                "timeline_builder.beat_sync_no_candidates",
                total=len(candidates),
                rejected=rejected_count,
                message="卡点选择：所有候选都被过滤",
            )
            return []

        # 第二步：获取视频动作档案并计算卡点分数
        scored_candidates: list[tuple[dict[str, Any], float, int]] = []

        for candidate in valid_candidates:
            video_id = str(candidate.get("source_video_id", ""))
            original_score = float(candidate.get("score", 0.0))

            # 尝试获取视频动作档案
            video_profile = None
            try:
                video_profile = await action_detector.analyze_video(video_id)
            except Exception as exc:
                self._logger.debug(
                    "timeline_builder.action_detect_failed",
                    video_id=video_id,
                    error=str(exc),
                )

            # 计算卡点对齐分数
            alignment = beat_aligner.calculate_alignment_score(
                candidate=candidate,
                lyric_start_ms=lyric_start_ms,
                beats=beats,
                video_profile=video_profile,
            )

            # 存储卡点偏移量供渲染使用
            candidate["beat_sync_offset_ms"] = alignment.offset_ms
            candidate["beat_sync_score"] = alignment.score
            candidate["beat_sync_details"] = alignment.details

            scored_candidates.append((candidate, alignment.score, alignment.offset_ms))

            self._logger.debug(
                "timeline_builder.beat_sync_scored",
                video_id=video_id,
                original_score=round(original_score, 3),
                beat_sync_score=round(alignment.score, 3),
                offset_ms=alignment.offset_ms,
                has_action_profile=video_profile is not None,
            )

        # 第三步：按综合评分降序排序
        scored_candidates.sort(key=lambda x: -x[1])

        # 选择 top N
        selected = [item[0] for item in scored_candidates[:limit]]

        if selected:
            self._logger.info(
                "timeline_builder.beat_sync_selected",
                total=len(candidates),
                valid=len(valid_candidates),
                selected=len(selected),
                top_score=round(scored_candidates[0][1], 3) if scored_candidates else 0,
                top_offset=scored_candidates[0][2] if scored_candidates else 0,
                message="卡点选择完成",
            )

        return selected

    async def _select_candidates_with_onset_sync(
        self,
        candidates: list[dict[str, Any]],
        limit: int,
        lyric_start_ms: int,
        lyric_end_ms: int,
        music_onsets: OnsetResult,
    ) -> list[dict[str, Any]]:
        """基于鼓点对齐选择候选视频（类似剪映自动卡点）。

        核心逻辑：
        1. 获取歌词时间段内的音乐鼓点
        2. 从视频音频中提取鼓点
        3. 计算最佳偏移使两者鼓点对齐
        4. 按对齐分数排序选择候选

        Args:
            candidates: 候选列表
            limit: 选择数量
            lyric_start_ms: 歌词开始时间
            lyric_end_ms: 歌词结束时间
            music_onsets: 整首歌曲的鼓点检测结果
        """
        if not candidates:
            return []

        # 第一步：应用去重过滤（与 beat_sync 相同）
        valid_candidates: list[dict[str, Any]] = []
        rejected_count = 0

        for candidate in candidates:
            video_id = str(candidate.get("source_video_id", ""))
            start_ms = int(candidate.get("start_time_ms", 0))
            end_ms = int(candidate.get("end_time_ms", 0))
            segment_key = (video_id, start_ms, end_ms)

            usage_count = self._used_segments.get(segment_key, 0)
            if usage_count > 0:
                rejected_count += 1
                continue

            has_overlap = False
            for used_key in self._used_segments.keys():
                used_video_id, used_start, used_end = used_key
                if used_video_id == video_id:
                    overlap_ratio = calculate_overlap_ratio(start_ms, end_ms, used_start, used_end)
                    if overlap_ratio > 0:
                        has_overlap = True
                        rejected_count += 1
                        break

            if has_overlap:
                continue

            valid_candidates.append(dict(candidate))

        if not valid_candidates:
            self._logger.warning(
                "timeline_builder.onset_sync_no_candidates",
                total=len(candidates),
                rejected=rejected_count,
            )
            return []

        # 第二步：只对 Top 3 候选计算鼓点对齐（避免分析全部候选导致太慢）
        # 先按 TwelveLabs 原始评分排序，取前 3 个
        valid_candidates.sort(key=lambda x: -float(x.get("score", 0.0)))
        top_candidates = valid_candidates[:3]

        self._logger.info(
            "timeline_builder.onset_sync_analyzing",
            total_valid=len(valid_candidates),
            analyzing=len(top_candidates),
            message=f"只分析前 {len(top_candidates)} 个候选的鼓点",
        )

        scored_candidates: list[tuple[dict[str, Any], float, int]] = []

        for candidate in top_candidates:
            video_id = str(candidate.get("source_video_id", ""))
            original_score = float(candidate.get("score", 0.0))

            # 获取视频流 URL 用于提取音频
            video_stream_url = None
            try:
                video_stream_url = video_fetcher._get_stream_url(video_id)
            except Exception as exc:
                self._logger.debug(
                    "timeline_builder.get_stream_url_failed",
                    video_id=video_id,
                    error=str(exc),
                )

            # 计算鼓点对齐分数
            alignment = await beat_aligner.calculate_onset_alignment(
                candidate=candidate,
                lyric_start_ms=lyric_start_ms,
                lyric_end_ms=lyric_end_ms,
                music_onsets=music_onsets,
                video_stream_url=video_stream_url,
            )

            # 存储对齐信息
            candidate["beat_sync_offset_ms"] = alignment.offset_ms
            candidate["beat_sync_score"] = alignment.score
            candidate["beat_sync_details"] = alignment.details

            scored_candidates.append((candidate, alignment.score, alignment.offset_ms))

            self._logger.debug(
                "timeline_builder.onset_sync_scored",
                video_id=video_id,
                original_score=round(original_score, 3),
                onset_sync_score=round(alignment.score, 3),
                offset_ms=alignment.offset_ms,
            )

        # 第三步：按对齐分数排序
        scored_candidates.sort(key=lambda x: -x[1])

        # 选择 top N
        selected = [item[0] for item in scored_candidates[:limit]]

        if selected:
            self._logger.info(
                "timeline_builder.onset_sync_selected",
                total=len(candidates),
                valid=len(valid_candidates),
                selected=len(selected),
                top_score=round(scored_candidates[0][1], 3) if scored_candidates else 0,
                top_offset=scored_candidates[0][2] if scored_candidates else 0,
                message="鼓点卡点选择完成",
            )

        return selected

    def _explode_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        exploded: list[dict[str, Any]] = []
        for seg in segments:
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            pieces = [
                piece.strip()
                for piece in self._split_pattern.split(text)
                if piece and piece.strip()
            ]
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

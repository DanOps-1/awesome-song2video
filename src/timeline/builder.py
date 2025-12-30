"""时间线构建器

将歌词与视频片段进行时间对齐。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

import structlog

from src.infra.config.settings import get_settings
from src.retrieval import VideoClip, create_retriever
from src.retrieval.protocol import VideoRetriever
from src.timeline.models import (
    Timeline,
    TimelineSegment,
    VideoCandidate,
)

logger = structlog.get_logger(__name__)


def calculate_overlap_ratio(start1: int, end1: int, start2: int, end2: int) -> float:
    """计算两个时间段的重叠比例

    Returns:
        重叠部分占较短片段的比例 (0.0 到 1.0)
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


class TimelineBuilder:
    """时间线构建器

    将歌词文本与视频片段对齐。

    注意：本地 Whisper ASR 已移除，歌词必须通过在线服务获取或手动导入。
    """

    def __init__(
        self,
        retriever: Optional[VideoRetriever] = None,
    ) -> None:
        """初始化时间线构建器

        Args:
            retriever: 视频检索器，默认从配置创建
        """
        self._settings = get_settings()
        self._retriever = retriever or create_retriever()

        # 缓存和去重
        self._candidate_cache: dict[tuple[str, int], List[VideoClip]] = {}
        self._used_segments: dict[tuple[str, int, int], int] = {}

        # 文本分割模式
        self._split_pattern = re.compile(r"(?:\r?\n)+|[，,。！？!?；;…]")

        # 非歌词内容识别
        self._non_lyric_patterns = [
            r"^作词[\s:：]",
            r"^词[\s:：]",
            r"^作曲[\s:：]",
            r"^曲[\s:：]",
            r"^编曲[\s:：]",
            r"^演唱[\s:：]",
            r"^制作[\s:：]",
            r"(?i)^lyrics\s+by",
            r"(?i)^music\s+by",
            r"(?i)^composed\s+by",
        ]

    async def build(
        self,
        audio_path: Optional[Path] = None,
        lyrics_text: Optional[str] = None,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Timeline:
        """构建时间线

        Args:
            audio_path: 音频文件路径
            lyrics_text: 歌词文本（如无音频）
            language: 语言代码
            prompt: 转录提示词

        Returns:
            时间线对象
        """
        self._candidate_cache.clear()
        self._used_segments.clear()

        # 获取转录结果或解析歌词
        segments = await self._get_segments(audio_path, lyrics_text, language, prompt)

        # 分割长片段
        segments = self._explode_segments(segments)
        segments = self._split_by_duration(segments, max_duration=12.0)

        # 标记非歌词内容
        self._mark_non_lyric_segments(segments)

        # 按时间排序
        segments.sort(key=lambda x: float(x.get("start", 0)))

        # 获取音频时长
        audio_duration_ms = 0
        if audio_path:
            audio_duration_ms = self._get_audio_duration(audio_path)

        # 构建时间线
        timeline = Timeline(audio_duration_ms=audio_duration_ms)
        cursor_ms = 0

        for seg in segments:
            text = str(seg.get("text", "")).strip()
            if not text:
                continue

            start_ms = int(float(seg.get("start", 0)) * 1000)
            end_ms = int(float(seg.get("end", start_ms / 1000 + 1)) * 1000)

            # 处理间隙
            if cursor_ms > 0 and start_ms > cursor_ms:
                gap = start_ms - cursor_ms
                if gap > 2000:
                    # 大间隙：插入间奏
                    gap_segment = await self._create_gap_segment(cursor_ms, start_ms)
                    timeline.add_segment(gap_segment)
                else:
                    # 小间隙：向前延伸
                    start_ms = cursor_ms

            # 搜索视频候选
            if seg.get("is_non_lyric", False):
                candidates = []
            else:
                search_query = seg.get("search_prompt", text)
                candidates = await self._search_candidates(
                    search_query,
                    start_ms,
                    end_ms,
                )

            # 创建片段
            segment = TimelineSegment(
                text=text,
                start_ms=start_ms,
                end_ms=end_ms,
                candidates=candidates,
                is_instrumental=False,
            )
            timeline.add_segment(segment)

            # 标记已使用
            for candidate in candidates:
                self._mark_used(candidate)

            cursor_ms = max(cursor_ms, end_ms)

        # 填充尾部
        if audio_duration_ms > cursor_ms + 1000:
            outro_segment = await self._create_gap_segment(
                cursor_ms,
                audio_duration_ms,
                prompt="ending music video, fade out, cinematic",
            )
            outro_segment.text = "(Outro)"
            timeline.add_segment(outro_segment)

        return timeline

    async def _get_segments(
        self,
        audio_path: Optional[Path],
        lyrics_text: Optional[str],
        language: Optional[str],
        prompt: Optional[str],
    ) -> List[dict]:
        """解析歌词文本为片段列表。

        注意：本地 Whisper ASR 已移除，歌词必须通过在线服务获取或手动导入。
        audio_path、language 和 prompt 参数保留仅为兼容性，不再使用。
        """
        if lyrics_text:
            segments = []
            for idx, line in enumerate(lyrics_text.splitlines()):
                stripped = line.strip()
                if stripped:
                    segments.append(
                        {
                            "text": stripped,
                            "start": float(idx),
                            "end": float(idx + 1),
                        }
                    )
            return segments
        else:
            raise ValueError("必须提供歌词文本（通过在线服务获取或手动导入）")

    async def _search_candidates(
        self,
        query: str,
        start_ms: int,
        end_ms: int,
        limit: int = 20,
    ) -> List[VideoCandidate]:
        """搜索视频候选"""
        cache_key = (query, limit)
        if cache_key not in self._candidate_cache:
            duration_hint_ms = end_ms - start_ms
            clips = await self._retriever.search(
                query=query,
                limit=limit,
                duration_hint_ms=duration_hint_ms,
            )
            self._candidate_cache[cache_key] = clips

        clips = self._candidate_cache[cache_key]

        # 转换并过滤
        candidates = []
        for clip in clips:
            candidate = self._normalize_candidate(clip, start_ms, end_ms)
            if candidate and self._is_candidate_valid(candidate):
                candidates.append(candidate)

        # 按评分排序并去重
        candidates.sort(key=lambda x: -x.score)
        selected = candidates[:3]

        # 如果没有候选，使用 fallback
        if not selected:
            selected = [self._create_fallback_candidate(start_ms, end_ms)]

        return selected

    def _normalize_candidate(
        self,
        clip: VideoClip,
        start_ms: int,
        end_ms: int,
    ) -> Optional[VideoCandidate]:
        """规范化候选片段"""
        lyric_duration = end_ms - start_ms
        api_duration = clip.duration_ms

        # 过滤时长严重不足的候选
        if lyric_duration >= 5000 and api_duration < lyric_duration * 0.5:
            return None

        # 从中间位置截取
        api_middle = clip.start_ms + (api_duration // 2)
        clip_start = api_middle - (lyric_duration // 2)
        clip_end = clip_start + lyric_duration

        # 边界调整
        if clip_start < clip.start_ms:
            clip_start = clip.start_ms
            clip_end = clip_start + lyric_duration

        return VideoCandidate(
            video_id=clip.video_id,
            start_ms=clip_start,
            end_ms=clip_end,
            score=clip.score,
            metadata=clip.metadata,
        )

    def _is_candidate_valid(self, candidate: VideoCandidate) -> bool:
        """检查候选是否有效（未被使用且无重叠）"""
        segment_key = (
            candidate.video_id,
            candidate.start_ms,
            candidate.end_ms,
        )

        # 检查精确匹配
        if self._used_segments.get(segment_key, 0) > 0:
            return False

        # 检查重叠
        for used_key in self._used_segments:
            used_video_id, used_start, used_end = used_key
            if used_video_id == candidate.video_id:
                overlap = calculate_overlap_ratio(
                    candidate.start_ms,
                    candidate.end_ms,
                    used_start,
                    used_end,
                )
                if overlap > 0:
                    return False

        return True

    def _mark_used(self, candidate: VideoCandidate) -> None:
        """标记候选为已使用"""
        segment_key = (
            candidate.video_id,
            candidate.start_ms,
            candidate.end_ms,
        )
        self._used_segments[segment_key] = self._used_segments.get(segment_key, 0) + 1

    def _create_fallback_candidate(
        self,
        start_ms: int,
        end_ms: int,
    ) -> VideoCandidate:
        """创建 fallback 候选"""
        return VideoCandidate(
            video_id=self._settings.fallback_video_id,
            start_ms=start_ms,
            end_ms=end_ms,
            score=0.0,
        )

    async def _create_gap_segment(
        self,
        start_ms: int,
        end_ms: int,
        prompt: str = "atmospheric music video, cinematic scenes",
    ) -> TimelineSegment:
        """创建间隙填充片段"""
        candidates = await self._search_candidates(prompt, start_ms, end_ms, limit=10)
        return TimelineSegment(
            text="(Instrumental)",
            start_ms=start_ms,
            end_ms=end_ms,
            candidates=candidates,
            is_instrumental=True,
        )

    def _mark_non_lyric_segments(self, segments: List[dict]) -> None:
        """标记非歌词内容"""
        for seg in segments:
            text = str(seg.get("text", "")).strip()
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            duration = end - start

            if self._is_non_lyric_text(text):
                if duration < 10.0:
                    seg["is_non_lyric"] = True
                else:
                    seg["is_non_lyric"] = False
                    seg["search_prompt"] = "cinematic music video intro, atmospheric"

    def _is_non_lyric_text(self, text: str) -> bool:
        """判断是否为非歌词内容"""
        for pattern in self._non_lyric_patterns:
            if re.search(pattern, text):
                return True
        return False

    def _get_audio_duration(self, audio_path: Path) -> int:
        """获取音频时长（毫秒）"""
        import subprocess

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(float(result.stdout.strip()) * 1000)
        except Exception as e:
            logger.warning("timeline.audio_duration_failed", error=str(e))
        return 0

    def _split_by_duration(
        self,
        segments: List[dict],
        max_duration: float = 12.0,
    ) -> List[dict]:
        """将过长片段切分为更小的片段"""
        result = []
        for seg in segments:
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            duration = end - start

            if duration <= max_duration:
                result.append(seg)
                continue

            num_chunks = int(duration // max_duration) + 1
            chunk_duration = duration / num_chunks

            for i in range(num_chunks):
                chunk_start = start + (i * chunk_duration)
                chunk_end = chunk_start + chunk_duration

                new_seg = seg.copy()
                new_seg["start"] = chunk_start
                new_seg["end"] = chunk_end
                result.append(new_seg)

        return result

    def _explode_segments(self, segments: List[dict]) -> List[dict]:
        """按标点符号分割长文本"""
        result = []
        for seg in segments:
            text = str(seg.get("text", "")).strip()
            if not text:
                continue

            pieces = [p.strip() for p in self._split_pattern.split(text) if p and p.strip()]

            if len(pieces) <= 1:
                result.append(seg)
                continue

            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", start + 1.0))
            duration = end - start
            total_chars = sum(len(p) for p in pieces) or len(pieces)

            cursor = start
            for idx, piece in enumerate(pieces):
                ratio = len(piece) / total_chars
                chunk_duration = duration * ratio
                chunk_end = end if idx == len(pieces) - 1 else cursor + chunk_duration

                result.append(
                    {
                        **seg,
                        "text": piece,
                        "start": cursor,
                        "end": chunk_end,
                    }
                )
                cursor = chunk_end

        return result

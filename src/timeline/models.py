"""时间线数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class VideoCandidate:
    """视频片段候选"""

    video_id: str
    start_ms: int
    end_ms: int
    score: float
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass
class TimelineSegment:
    """时间线片段

    表示歌词与视频的对应关系。
    """

    text: str
    start_ms: int
    end_ms: int
    candidates: List[VideoCandidate] = field(default_factory=list)
    is_instrumental: bool = False

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def primary_candidate(self) -> Optional[VideoCandidate]:
        """获取主要候选（第一个）"""
        return self.candidates[0] if self.candidates else None


@dataclass
class Timeline:
    """完整时间线"""

    segments: List[TimelineSegment] = field(default_factory=list)
    audio_duration_ms: int = 0

    @property
    def total_duration_ms(self) -> int:
        if not self.segments:
            return 0
        return max(seg.end_ms for seg in self.segments)

    def add_segment(self, segment: TimelineSegment) -> None:
        """添加片段"""
        self.segments.append(segment)

    def get_gaps(self, threshold_ms: int = 1000) -> List[tuple[int, int]]:
        """检测时间线中的间隙

        Args:
            threshold_ms: 最小间隙阈值

        Returns:
            间隙列表 [(start_ms, end_ms), ...]
        """
        if not self.segments:
            return []

        gaps = []
        sorted_segs = sorted(self.segments, key=lambda s: s.start_ms)

        # 检查开头间隙
        if sorted_segs[0].start_ms > threshold_ms:
            gaps.append((0, sorted_segs[0].start_ms))

        # 检查中间间隙
        for i in range(len(sorted_segs) - 1):
            gap_start = sorted_segs[i].end_ms
            gap_end = sorted_segs[i + 1].start_ms
            if gap_end - gap_start > threshold_ms:
                gaps.append((gap_start, gap_end))

        # 检查结尾间隙
        if self.audio_duration_ms > 0:
            last_end = sorted_segs[-1].end_ms
            if self.audio_duration_ms - last_end > threshold_ms:
                gaps.append((last_end, self.audio_duration_ms))

        return gaps


@dataclass
class RenderLine:
    """渲染行

    用于视频渲染的最终数据格式。
    """

    source_video_id: str
    start_time_ms: int
    end_time_ms: int
    lyrics: str
    lyric_start_ms: int
    lyric_end_ms: int
    candidates: Optional[List[VideoCandidate]] = None

    @classmethod
    def from_segment(cls, segment: TimelineSegment) -> "RenderLine":
        """从时间线片段创建渲染行"""
        primary = segment.primary_candidate
        if primary:
            return cls(
                source_video_id=primary.video_id,
                start_time_ms=primary.start_ms,
                end_time_ms=primary.end_ms,
                lyrics=segment.text,
                lyric_start_ms=segment.start_ms,
                lyric_end_ms=segment.end_ms,
                candidates=segment.candidates,
            )
        else:
            return cls(
                source_video_id="",
                start_time_ms=segment.start_ms,
                end_time_ms=segment.end_ms,
                lyrics=segment.text,
                lyric_start_ms=segment.start_ms,
                lyric_end_ms=segment.end_ms,
                candidates=[],
            )

"""时间线构建模块

提供歌词到视频片段的时间线映射功能。
"""

from src.timeline.models import (
    Timeline,
    TimelineSegment,
    VideoCandidate,
    RenderLine,
)
from src.timeline.builder import TimelineBuilder
from src.timeline.edl_writer import EDLWriter

__all__ = [
    "Timeline",
    "TimelineSegment",
    "VideoCandidate",
    "RenderLine",
    "TimelineBuilder",
    "EDLWriter",
]

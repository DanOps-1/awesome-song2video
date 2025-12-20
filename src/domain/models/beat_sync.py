"""节拍同步相关数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class BeatAnalysisData(SQLModel, table=True):
    """节拍分析数据存储。

    存储音频的节拍分析结果，用于视频卡点对齐。
    """

    __tablename__ = "beat_analysis_data"

    id: str = Field(primary_key=True)
    mix_request_id: str = Field(foreign_key="song_mix_requests.id", unique=True)
    bpm: float = Field(default=0.0)
    beat_times_ms: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    downbeat_times_ms: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    beat_strength: list[float] = Field(default_factory=list, sa_column=Column(JSON))
    tempo_stability: float = Field(default=0.0)
    enabled: bool = Field(default=True)  # 用户是否启用卡点功能
    created_at: datetime = Field(default_factory=datetime.utcnow)


class VideoActionCache(SQLModel, table=True):
    """视频动作分析缓存。

    缓存 TwelveLabs 或 FFmpeg 分析的视频动作高光点，
    避免重复分析同一视频。
    """

    __tablename__ = "video_action_cache"

    video_id: str = Field(primary_key=True)
    action_points: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    scene_changes: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    motion_intensity: list[tuple[int, float]] = Field(default_factory=list, sa_column=Column(JSON))
    analyzed_at: Optional[datetime] = Field(default=None)
    analysis_source: str = Field(default="unknown")  # "twelvelabs" or "ffmpeg"

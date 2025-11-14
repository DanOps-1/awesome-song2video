"""混剪相关 SQLModel 实体。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class VideoSegmentMatch(SQLModel, table=True):
    __tablename__ = "video_segment_matches"

    id: str = Field(primary_key=True)
    line_id: str = Field(foreign_key="lyric_lines.id")
    source_video_id: str
    index_id: str
    start_time_ms: int
    end_time_ms: int
    score: float
    tags: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    preview_url: Optional[str] = None
    generated_by: str
    created_at: datetime | None = Field(default_factory=datetime.utcnow)


class LyricLine(SQLModel, table=True):
    __tablename__ = "lyric_lines"

    id: str = Field(primary_key=True)
    mix_request_id: str = Field(foreign_key="song_mix_requests.id")
    line_no: int
    original_text: str
    translated_text: Optional[str] = None
    start_time_ms: int
    end_time_ms: int
    auto_confidence: Optional[float] = None
    selected_segment_id: Optional[str] = Field(default=None, foreign_key="video_segment_matches.id")
    status: str = Field(default="pending")
    annotations: Optional[str] = None
    audit_log: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))
    # 运行时赋值的候选片段列表（非持久化字段）


class SongMixRequest(SQLModel, table=True):
    __tablename__ = "song_mix_requests"

    id: str = Field(primary_key=True)
    song_title: str
    artist: Optional[str] = None
    source_type: str
    audio_asset_id: Optional[str] = None
    lyrics_text: str
    language: str
    timeline_status: str = Field(default="pending")
    render_status: str = Field(default="idle")
    priority: int = Field(default=5)
    owner_id: str
    error_codes: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    metrics: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime | None = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(default_factory=datetime.utcnow)

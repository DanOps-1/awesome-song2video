"""混剪相关 SQLModel 实体。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, cast

from pydantic import PrivateAttr
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
    _candidates: list[VideoSegmentMatch] = PrivateAttr(default_factory=list)

    @property
    def candidates(self) -> list[VideoSegmentMatch]:
        private = getattr(self, "__pydantic_private__", None)
        if private is None or "_candidates" not in private:
            self.__pydantic_private__ = {"_candidates": []}
            return []
        return cast(list[VideoSegmentMatch], private["_candidates"])

    @candidates.setter
    def candidates(self, value: list[VideoSegmentMatch]) -> None:
        private = getattr(self, "__pydantic_private__", None)
        if private is None:
            self.__pydantic_private__ = {"_candidates": value}
        else:
            private["_candidates"] = value


class SongMixRequest(SQLModel, table=True):
    """混剪任务。

    timeline_status 状态流转：
    - pending: 初始状态
    - transcribing: Whisper 识别中
    - transcribed: 识别完成，等待用户确认歌词
    - matching: 视频匹配中
    - generated: 匹配完成
    """
    __tablename__ = "song_mix_requests"

    id: str = Field(primary_key=True)
    song_title: str
    artist: Optional[str] = None
    source_type: str
    audio_asset_id: Optional[str] = None
    lyrics_text: str
    language: str
    timeline_status: str = Field(default="pending")
    timeline_progress: float = Field(default=0.0)  # 时间线生成进度 0-100
    lyrics_confirmed: bool = Field(default=False)  # 歌词是否已确认
    render_status: str = Field(default="idle")
    priority: int = Field(default=5)
    owner_id: str
    error_codes: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    metrics: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime | None = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(default_factory=datetime.utcnow)

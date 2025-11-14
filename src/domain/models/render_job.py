"""渲染任务 SQLModel。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class RenderJob(SQLModel, table=True):
    __tablename__ = "render_jobs"

    id: str = Field(primary_key=True)
    mix_request_id: str = Field(foreign_key="song_mix_requests.id")
    job_status: str = Field(default="queued")
    worker_node: Optional[str] = None
    ffmpeg_script: str
    progress: float = Field(default=0.0)
    output_asset_id: Optional[str] = None
    error_log: Optional[str] = None
    submitted_at: datetime | None = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    metrics: Optional[dict[str, str]] = Field(default=None, sa_column=Column(JSON))

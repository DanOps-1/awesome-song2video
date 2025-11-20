#!/usr/bin/env python
"""Pytest fixtures for lyrics mix project."""
# ruff: noqa: E402

import asyncio
import sys
import uuid
from collections.abc import AsyncGenerator, Callable, Generator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.api.main import app
from src.domain.models.render_job import RenderJob
from src.domain.models.song_mix import LyricLine, SongMixRequest, VideoSegmentMatch
from src.infra.persistence.database import init_engine, init_models


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database(event_loop: asyncio.AbstractEventLoop) -> None:
    init_engine("sqlite+aiosqlite:///:memory:")
    event_loop.run_until_complete(init_models())


@pytest.fixture
async def app_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# =============================================================================
# Factory Fixtures for Testing (Phase 2 - T008)
# =============================================================================


@pytest.fixture
def mix_request_factory() -> Callable[..., SongMixRequest]:
    """创建 SongMixRequest 的工厂函数。"""

    def _create(
        mix_id: str | None = None,
        song_title: str = "测试歌曲",
        owner_id: str = "test-user",
        timeline_status: str = "generated",
        render_status: str = "idle",
        metrics: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SongMixRequest:
        return SongMixRequest(
            id=mix_id or str(uuid.uuid4()),
            song_title=song_title,
            source_type="upload",
            lyrics_text="测试歌词内容",
            language="zh",
            timeline_status=timeline_status,
            render_status=render_status,
            owner_id=owner_id,
            metrics=metrics,
            **kwargs,
        )

    return _create


@pytest.fixture
def lyric_line_factory() -> Callable[..., LyricLine]:
    """创建 LyricLine 的工厂函数。"""

    def _create(
        line_id: str | None = None,
        mix_request_id: str = "test-mix-id",
        line_no: int = 1,
        original_text: str = "测试歌词行",
        start_time_ms: int = 0,
        end_time_ms: int = 3000,
        status: str = "locked",
        selected_segment_id: str | None = None,
        **kwargs: Any,
    ) -> LyricLine:
        return LyricLine(
            id=line_id or str(uuid.uuid4()),
            mix_request_id=mix_request_id,
            line_no=line_no,
            original_text=original_text,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            status=status,
            selected_segment_id=selected_segment_id,
            **kwargs,
        )

    return _create


@pytest.fixture
def video_segment_match_factory() -> Callable[..., VideoSegmentMatch]:
    """创建 VideoSegmentMatch 的工厂函数。"""

    def _create(
        match_id: str | None = None,
        line_id: str = "test-line-id",
        source_video_id: str = "6911acda8bf751b791733149",
        index_id: str = "6911aaadd68fb776bc1bd8e7",
        start_time_ms: int = 1000,
        end_time_ms: int = 4000,
        score: float = 0.85,
        generated_by: str = "auto",
        **kwargs: Any,
    ) -> VideoSegmentMatch:
        return VideoSegmentMatch(
            id=match_id or str(uuid.uuid4()),
            line_id=line_id,
            source_video_id=source_video_id,
            index_id=index_id,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            score=score,
            generated_by=generated_by,
            **kwargs,
        )

    return _create


@pytest.fixture
def render_job_factory() -> Callable[..., RenderJob]:
    """创建 RenderJob 的工厂函数。"""

    def _create(
        job_id: str | None = None,
        mix_request_id: str = "test-mix-id",
        job_status: str = "queued",
        ffmpeg_script: str = "# test ffmpeg script",
        output_asset_id: str | None = None,
        metrics: dict[str, Any] | None = None,
        submitted_at: datetime | None = None,
        finished_at: datetime | None = None,
        **kwargs: Any,
    ) -> RenderJob:
        return RenderJob(
            id=job_id or str(uuid.uuid4()),
            mix_request_id=mix_request_id,
            job_status=job_status,
            ffmpeg_script=ffmpeg_script,
            output_asset_id=output_asset_id,
            metrics=metrics,
            submitted_at=submitted_at or datetime.utcnow(),
            finished_at=finished_at,
            **kwargs,
        )

    return _create

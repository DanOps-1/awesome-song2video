from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest

from src.domain.models.render_job import RenderJob
from src.domain.models.song_mix import LyricLine, SongMixRequest, VideoSegmentMatch
from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.workers import render_worker


@pytest.mark.asyncio
async def test_render_pipeline_with_placeholder(
    monkeypatch: pytest.MonkeyPatch,
    mix_request_factory: Callable[..., SongMixRequest],
    lyric_line_factory: Callable[..., LyricLine],
    video_segment_match_factory: Callable[..., VideoSegmentMatch],
    render_job_factory: Callable[..., RenderJob],
) -> None:
    song_repo = SongMixRepository()
    mix = mix_request_factory()
    await song_repo.create_request(mix)

    lines = []
    candidates = []
    for idx in range(3):
        line = lyric_line_factory(
            line_id=f"line-{idx}-{uuid4()}"[:18], line_no=idx + 1, mix_request_id=mix.id
        )
        lines.append(line)
        candidates.append(
            video_segment_match_factory(
                match_id=f"match-{idx}-{uuid4()}"[:18],
                line_id=line.id,
                source_video_id=f"video-{idx}",
                start_time_ms=0,
                end_time_ms=1500,
            )
        )
    await song_repo.bulk_insert_lines(lines)
    await song_repo.attach_candidates(candidates)

    job_repo = RenderJobRepository()
    job = render_job_factory(mix_request_id=mix.id)
    await job_repo.save(job)

    call_count = {"fail": 0}

    def flaky_fetch(video_id: str, start_ms: int, end_ms: int, target: Path) -> Path:
        call_count["fail"] += 1
        raise RuntimeError("cdn_unavailable")

    monkeypatch.setattr(render_worker.video_fetcher, "fetch_clip", flaky_fetch)
    monkeypatch.setattr(
        "src.workers.render_worker._run_ffmpeg", lambda cmd: Path(cmd[-1]).write_text("video")
    )
    monkeypatch.setattr(
        "src.workers.render_worker._attach_audio_track", lambda *args, **kwargs: None
    )
    monkeypatch.setattr("src.workers.render_worker._resolve_audio_path", lambda mix: None)
    monkeypatch.setattr(
        "src.services.render.placeholder_manager.write_placeholder_clip",
        lambda target, duration: target.write_text("placeholder"),
    )

    await render_worker._render_mix_impl(job.id)

    refreshed = await job_repo.get(job.id)
    assert refreshed is not None
    assert refreshed.metrics is not None
    clip_stats = refreshed.metrics["render"]["clip_stats"]
    assert clip_stats["placeholder_tasks"] == 3

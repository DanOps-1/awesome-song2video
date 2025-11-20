from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from src.domain.models.render_job import RenderJob
from src.domain.models.song_mix import LyricLine, SongMixRequest, VideoSegmentMatch
from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.workers import render_worker


@pytest.mark.asyncio
async def test_parallel_clip_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    mix_request_factory: Callable[..., SongMixRequest],
    lyric_line_factory: Callable[..., LyricLine],
    video_segment_match_factory: Callable[..., VideoSegmentMatch],
    render_job_factory: Callable[..., RenderJob],
) -> None:
    song_repo = SongMixRepository()
    mix = mix_request_factory()
    await song_repo.create_request(mix)

    lines: list[LyricLine] = []
    candidates = []
    for idx in range(60):
        line = lyric_line_factory(line_id=f"line-{idx}", line_no=idx + 1, mix_request_id=mix.id)
        lines.append(line)
        candidates.append(
            video_segment_match_factory(
                match_id=f"match-{idx}",
                line_id=line.id,
                source_video_id=f"video-{idx % 5}",
                start_time_ms=idx * 1000,
                end_time_ms=idx * 1000 + 1500,
            )
        )
    await song_repo.bulk_insert_lines(lines)
    await song_repo.attach_candidates(candidates)

    job_repo = RenderJobRepository()
    job = render_job_factory(mix_request_id=mix.id)
    await job_repo.save(job)

    counter = {"current": 0, "max": 0}
    lock = threading.Lock()

    def fake_fetch(video_id: str, start_ms: int, end_ms: int, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        with lock:
            counter["current"] += 1
            counter["max"] = max(counter["max"], counter["current"])
        time.sleep(0.005)
        target.write_text("clip")
        with lock:
            counter["current"] -= 1
        return target

    def fake_run_ffmpeg(cmd: list[str]) -> None:
        output = Path(cmd[-1])
        output.write_text("video")

    def fake_attach(video_path: Path, audio_path: Path, target_path: Path) -> None:
        target_path.write_text("video")

    monkeypatch.setattr(render_worker.video_fetcher, "fetch_clip", fake_fetch)
    monkeypatch.setattr("src.workers.render_worker._run_ffmpeg", fake_run_ffmpeg)
    monkeypatch.setattr("src.workers.render_worker._attach_audio_track", fake_attach)
    monkeypatch.setattr("src.workers.render_worker._resolve_audio_path", lambda mix: None)

    await render_worker._render_mix_impl(job.id)

    refreshed = await job_repo.get(job.id)
    assert refreshed is not None
    assert refreshed.metrics is not None
    clip_stats = refreshed.metrics["render"]["clip_stats"]
    assert clip_stats["total_tasks"] == 60
    assert clip_stats["failed_tasks"] == 0
    assert clip_stats["peak_parallelism"] <= render_worker.clip_config.max_parallelism

    assert counter["max"] <= render_worker.clip_config.max_parallelism

    output_dir = Path("artifacts/renders")
    for suffix in (".mp4", ".srt"):
        path = output_dir / f"{job.id}{suffix}"
        if path.exists():
            path.unlink()

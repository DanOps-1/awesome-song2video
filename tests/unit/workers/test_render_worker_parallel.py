import asyncio
from pathlib import Path

import pytest

from src.domain.services.render_clip_scheduler import (
    ClipDownloadResult,
    ClipDownloadTask,
    RenderClipScheduler,
)


@pytest.mark.asyncio
async def test_scheduler_limits_global_parallelism(tmp_path: Path) -> None:
    scheduler = RenderClipScheduler(
        max_parallelism=2,
        per_video_limit=2,
        max_retry=1,
        retry_backoff_base_ms=1,
    )

    running = 0
    max_seen = 0

    async def fake_worker(task: ClipDownloadTask) -> ClipDownloadResult:
        nonlocal running, max_seen
        running += 1
        max_seen = max(max_seen, running)
        await asyncio.sleep(0.01)
        running -= 1
        return ClipDownloadResult(task=task, status="success", path=task.target_path)

    tasks = [
        ClipDownloadTask(
            idx=i,
            video_id="vid-global",
            start_ms=0,
            end_ms=1000,
            target_path=tmp_path / f"clip_{i}.mp4",
        )
        for i in range(5)
    ]

    results = await scheduler.run(tasks, fake_worker)

    assert all(r.status == "success" for r in results)
    assert max_seen <= 2


@pytest.mark.asyncio
async def test_scheduler_retries_failures(tmp_path: Path) -> None:
    scheduler = RenderClipScheduler(
        max_parallelism=3,
        per_video_limit=1,
        max_retry=2,
        retry_backoff_base_ms=1,
    )

    attempts: dict[int, int] = {}

    async def flaky_worker(task: ClipDownloadTask) -> ClipDownloadResult:
        attempts[task.idx] = attempts.get(task.idx, 0) + 1
        if task.idx == 0 and attempts[task.idx] <= 2:
            raise RuntimeError("transient")
        return ClipDownloadResult(
            task=task,
            status="success",
            path=task.target_path,
        )

    tasks = [
        ClipDownloadTask(
            idx=i,
            video_id="vid-dup" if i == 0 else "vid-other",
            start_ms=0,
            end_ms=1000,
            target_path=tmp_path / f"clip_{i}.mp4",
        )
        for i in range(2)
    ]

    results = await scheduler.run(tasks, flaky_worker)

    assert attempts[0] == 3  # initial + 2 retries
    assert all(r.status == "success" for r in results)

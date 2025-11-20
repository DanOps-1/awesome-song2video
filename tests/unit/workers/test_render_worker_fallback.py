from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.domain.services.render_clip_scheduler import ClipDownloadResult, ClipDownloadTask
from src.workers import render_worker


class FakeScheduler:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._tasks: list[ClipDownloadTask] = []

    async def run(self, tasks: list[ClipDownloadTask], worker: Any) -> list[ClipDownloadResult]:
        self._tasks = tasks
        success_task = tasks[0]
        failed_task = tasks[1]
        success_path = success_task.target_path
        success_path.write_text("clip")
        return [
            ClipDownloadResult(task=success_task, status="success", path=success_path, duration_ms=10),
            ClipDownloadResult(task=failed_task, status="failed", path=None),
        ]


@pytest.mark.asyncio
async def test_extract_clips_inserts_placeholder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lines = [
        render_worker.RenderLine(
            source_video_id="v1",
            start_time_ms=0,
            end_time_ms=1000,
            lyrics="a",
            lyric_start_ms=0,
            lyric_end_ms=1000,
        ),
        render_worker.RenderLine(
            source_video_id="v2",
            start_time_ms=0,
            end_time_ms=1500,
            lyrics="b",
            lyric_start_ms=0,
            lyric_end_ms=1500,
        ),
    ]

    monkeypatch.setattr(render_worker, "RenderClipScheduler", FakeScheduler)
    monkeypatch.setattr(render_worker, "write_placeholder_clip", lambda target, duration: target.write_text("placeholder"))

    clips, stats = await render_worker._extract_clips(lines, "job-test", tmp_path)

    assert len(clips) == 2
    assert stats["placeholder_tasks"] == 1
    assert clips[1].read_text() == "placeholder"

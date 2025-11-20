"""并行剪辑任务调度器。"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from uuid import uuid4
from pathlib import Path
from typing import Awaitable, Callable, Literal

import structlog


logger = structlog.get_logger(__name__)
ClipStatus = Literal["success", "failed", "fallback-local", "fallback-placeholder"]


@dataclass
class ClipDownloadTask:
    idx: int
    video_id: str
    start_ms: int
    end_ms: int
    target_path: Path
    attempts: int = 0
    clip_task_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class ClipDownloadResult:
    task: ClipDownloadTask
    status: ClipStatus
    path: Path | None = None
    error: str | None = None
    duration_ms: float | None = None


ClipWorker = Callable[[ClipDownloadTask], Awaitable[ClipDownloadResult]]


class RenderClipScheduler:
    def __init__(
        self,
        *,
        max_parallelism: int,
        per_video_limit: int,
        max_retry: int,
        retry_backoff_base_ms: int,
    ) -> None:
        self._max_parallelism = max(1, max_parallelism)
        self._per_video_limit = max(1, per_video_limit)
        self._max_retry = max_retry
        self._retry_backoff_base = retry_backoff_base_ms / 1000.0

    async def run(self, tasks: list[ClipDownloadTask], worker: ClipWorker) -> list[ClipDownloadResult]:
        queue: asyncio.Queue[ClipDownloadTask | None] = asyncio.Queue()
        for task in tasks:
            queue.put_nowait(task)

        results: list[ClipDownloadResult] = []
        results_lock = asyncio.Lock()
        video_semaphores: dict[str, asyncio.Semaphore] = {}

        def get_video_semaphore(video_id: str) -> asyncio.Semaphore:
            if video_id not in video_semaphores:
                video_semaphores[video_id] = asyncio.Semaphore(self._per_video_limit)
            return video_semaphores[video_id]

        async def worker_loop() -> None:
            while True:
                task = await queue.get()
                if task is None:
                    queue.task_done()
                    break
                video_sem = get_video_semaphore(task.video_id)
                try:
                    if video_sem.locked():
                        logger.info(
                            "render_worker.per_video_limit_wait",
                            video_id=task.video_id,
                            limit=self._per_video_limit,
                        )
                    async with video_sem:
                        result = await worker(task)
                except Exception as exc:  # noqa: BLE001
                    if task.attempts < self._max_retry:
                        task.attempts += 1
                        await asyncio.sleep(self._backoff_seconds(task.attempts))
                        queue.put_nowait(task)
                        queue.task_done()
                        continue
                    result = ClipDownloadResult(task=task, status="failed", error=str(exc))
                async with results_lock:
                    results.append(result)
                queue.task_done()

        workers = [asyncio.create_task(worker_loop()) for _ in range(self._max_parallelism)]
        await queue.join()
        for _ in workers:
            queue.put_nowait(None)
        await asyncio.gather(*workers)
        return results

    def _backoff_seconds(self, attempts: int) -> float:
        return self._retry_backoff_base * math.pow(2, max(attempts - 1, 0))

"""系统监控 Admin API。"""

from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from src.infra.config.settings import get_settings
from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository


router = APIRouter(prefix="/system", tags=["admin-system"])
settings = get_settings()
mix_repo = SongMixRepository()
job_repo = RenderJobRepository()


class TaskStats(BaseModel):
    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    success_rate: float


class RenderStats(BaseModel):
    total_jobs: int
    completed: int
    failed: int
    in_progress: int
    average_duration_ms: float | None


class StorageStats(BaseModel):
    video_count: int
    video_size_bytes: int
    audio_count: int
    audio_size_bytes: int


class SystemStats(BaseModel):
    tasks: TaskStats
    renders: RenderStats
    storage: StorageStats
    uptime_seconds: float
    last_updated: datetime


class ServiceHealth(BaseModel):
    name: str
    status: str
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    services: list[ServiceHealth]
    timestamp: datetime


# 记录启动时间
_startup_time = datetime.now(UTC)


def _scan_storage() -> StorageStats:
    """扫描存储统计。"""
    video_dir = Path(settings.video_asset_dir)
    audio_dir = Path(settings.audio_asset_dir)

    video_count = 0
    video_size = 0
    audio_count = 0
    audio_size = 0

    if video_dir.exists():
        for path in video_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
                video_count += 1
                video_size += path.stat().st_size

    if audio_dir.exists():
        for path in audio_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in (".mp3", ".wav", ".flac", ".m4a", ".aac"):
                audio_count += 1
                audio_size += path.stat().st_size

    return StorageStats(
        video_count=video_count,
        video_size_bytes=video_size,
        audio_count=audio_count,
        audio_size_bytes=audio_size,
    )


@router.get("/stats", response_model=SystemStats)
async def get_system_stats() -> SystemStats:
    """获取系统统计信息。"""
    # 任务统计
    all_tasks = await mix_repo.list_requests()
    task_total = len(all_tasks)
    task_pending = sum(1 for t in all_tasks if t.timeline_status == "pending")
    task_processing = sum(1 for t in all_tasks if t.timeline_status == "processing")
    task_completed = sum(1 for t in all_tasks if t.render_status == "completed")
    task_failed = sum(
        1 for t in all_tasks if t.timeline_status == "failed" or t.render_status == "failed"
    )
    task_success_rate = (task_completed / task_total * 100) if task_total > 0 else 0.0

    # 渲染统计
    all_jobs = await job_repo.list_all()
    job_total = len(all_jobs)
    job_completed = sum(1 for j in all_jobs if j.job_status in ("success", "completed"))
    job_failed = sum(1 for j in all_jobs if j.job_status == "failed")
    job_in_progress = sum(1 for j in all_jobs if j.job_status in ("queued", "running"))

    # 计算平均渲染时长
    durations = []
    for job in all_jobs:
        if job.finished_at and job.submitted_at:
            duration = (job.finished_at - job.submitted_at).total_seconds() * 1000
            durations.append(duration)
    avg_duration = sum(durations) / len(durations) if durations else None

    # 存储统计
    storage = _scan_storage()

    # 运行时间
    uptime = (datetime.now(UTC) - _startup_time).total_seconds()

    return SystemStats(
        tasks=TaskStats(
            total=task_total,
            pending=task_pending,
            processing=task_processing,
            completed=task_completed,
            failed=task_failed,
            success_rate=task_success_rate,
        ),
        renders=RenderStats(
            total_jobs=job_total,
            completed=job_completed,
            failed=job_failed,
            in_progress=job_in_progress,
            average_duration_ms=avg_duration,
        ),
        storage=storage,
        uptime_seconds=uptime,
        last_updated=datetime.utcnow(),
    )


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """获取服务健康状态。"""
    services: list[ServiceHealth] = []

    # 检查数据库
    try:
        start = datetime.utcnow()
        await mix_repo.list_requests()
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        services.append(ServiceHealth(name="database", status="healthy", latency_ms=latency))
    except Exception as e:
        services.append(ServiceHealth(name="database", status="unhealthy", error=str(e)))

    # 检查视频目录
    video_dir = Path(settings.video_asset_dir)
    if video_dir.exists():
        services.append(ServiceHealth(name="video_storage", status="healthy"))
    else:
        services.append(
            ServiceHealth(name="video_storage", status="unhealthy", error="Directory not found")
        )

    # 检查音频目录
    audio_dir = Path(settings.audio_asset_dir)
    if audio_dir.exists():
        services.append(ServiceHealth(name="audio_storage", status="healthy"))
    else:
        services.append(
            ServiceHealth(name="audio_storage", status="unhealthy", error="Directory not found")
        )

    # 检查 TwelveLabs
    if settings.tl_api_key:
        services.append(ServiceHealth(name="twelvelabs", status="configured"))
    else:
        services.append(
            ServiceHealth(name="twelvelabs", status="not_configured", error="API key not set")
        )

    # 总体状态
    overall_status = "healthy"
    critical_services = ["database"]
    for svc in services:
        if svc.name in critical_services and svc.status == "unhealthy":
            overall_status = "unhealthy"
            break

    return HealthResponse(
        status=overall_status,
        services=services,
        timestamp=datetime.utcnow(),
    )

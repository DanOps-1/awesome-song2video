"""任务管理 Admin API。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.services.timeline_editor import TimelineEditor


router = APIRouter(prefix="/tasks", tags=["admin-tasks"])
mix_repo = SongMixRepository()
job_repo = RenderJobRepository()
editor = TimelineEditor()


class TaskSummary(BaseModel):
    id: str
    song_title: str
    artist: str | None
    timeline_status: str
    render_status: str
    created_at: datetime | None
    updated_at: datetime | None


class TaskStats(BaseModel):
    total: int
    pending: int
    processing: int
    completed: int
    failed: int


class TaskListResponse(BaseModel):
    tasks: list[TaskSummary]
    stats: TaskStats
    page: int
    page_size: int
    total_pages: int


class RenderJobSummary(BaseModel):
    id: str
    job_status: str
    progress: float
    submitted_at: datetime | None
    finished_at: datetime | None
    error_log: str | None


class LineDetail(BaseModel):
    id: str
    line_no: int
    original_text: str
    start_time_ms: int
    end_time_ms: int
    status: str
    selected_segment_id: str | None
    candidates_count: int


class TaskDetail(BaseModel):
    id: str
    song_title: str
    artist: str | None
    source_type: str
    audio_asset_id: str | None
    language: str
    timeline_status: str
    render_status: str
    priority: int
    owner_id: str
    error_codes: dict[str, Any] | None
    metrics: dict[str, Any] | None
    created_at: datetime | None
    updated_at: datetime | None
    lines: list[LineDetail]
    render_jobs: list[RenderJobSummary]


class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str
    details: dict[str, Any] | None = None


class TaskLogsResponse(BaseModel):
    task_id: str
    logs: list[LogEntry]


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[str | None, Query()] = None,
    keyword: Annotated[str | None, Query()] = None,
) -> TaskListResponse:
    """获取任务列表。"""
    all_tasks = await mix_repo.list_requests()

    # 筛选
    filtered = all_tasks
    if status:
        if status in ("pending", "processing", "generated", "failed"):
            filtered = [t for t in filtered if t.timeline_status == status]
        elif status == "completed":
            filtered = [t for t in filtered if t.render_status == "completed"]

    if keyword:
        keyword_lower = keyword.lower()
        filtered = [
            t
            for t in filtered
            if keyword_lower in t.song_title.lower()
            or (t.artist and keyword_lower in t.artist.lower())
        ]

    # 统计
    stats = TaskStats(
        total=len(all_tasks),
        pending=sum(1 for t in all_tasks if t.timeline_status == "pending"),
        processing=sum(1 for t in all_tasks if t.timeline_status == "processing"),
        completed=sum(1 for t in all_tasks if t.render_status == "completed"),
        failed=sum(
            1
            for t in all_tasks
            if t.timeline_status == "failed" or t.render_status == "failed"
        ),
    )

    # 分页
    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    page_tasks = filtered[start:end]

    return TaskListResponse(
        tasks=[
            TaskSummary(
                id=t.id,
                song_title=t.song_title,
                artist=t.artist,
                timeline_status=t.timeline_status,
                render_status=t.render_status,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in page_tasks
        ],
        stats=stats,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(task_id: Annotated[str, Path()]) -> TaskDetail:
    """获取任务详情。"""
    task = await mix_repo.get_request(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # 获取歌词行
    lines_data = await editor.list_lines(task_id)
    lines = [
        LineDetail(
            id=line["id"],
            line_no=line["line_no"],
            original_text=line["original_text"],
            start_time_ms=line["start_time_ms"],
            end_time_ms=line["end_time_ms"],
            status=line["status"],
            selected_segment_id=line.get("selected_segment_id"),
            candidates_count=len(line.get("candidates", [])),
        )
        for line in lines_data
    ]

    # 获取渲染任务
    render_jobs = await job_repo.list_by_mix(task_id)
    jobs = [
        RenderJobSummary(
            id=job.id,
            job_status=job.job_status,
            progress=job.progress,
            submitted_at=job.submitted_at,
            finished_at=job.finished_at,
            error_log=job.error_log,
        )
        for job in render_jobs
    ]

    return TaskDetail(
        id=task.id,
        song_title=task.song_title,
        artist=task.artist,
        source_type=task.source_type,
        audio_asset_id=task.audio_asset_id,
        language=task.language,
        timeline_status=task.timeline_status,
        render_status=task.render_status,
        priority=task.priority,
        owner_id=task.owner_id,
        error_codes=task.error_codes,
        metrics=task.metrics,
        created_at=task.created_at,
        updated_at=task.updated_at,
        lines=lines,
        render_jobs=jobs,
    )


@router.post("/{task_id}/retry", status_code=202)
async def retry_task(task_id: Annotated[str, Path()]) -> dict[str, str]:
    """重试失败的任务。"""
    task = await mix_repo.get_request(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.timeline_status not in ("failed",) and task.render_status not in ("failed",):
        raise HTTPException(status_code=400, detail="Task is not in failed state")

    # 重置状态
    await mix_repo.update_status(task_id, timeline_status="pending", render_status="idle")

    return {"message": "Task queued for retry", "task_id": task_id}


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: Annotated[str, Path()]) -> None:
    """删除任务。"""
    task = await mix_repo.get_request(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    await mix_repo.delete_request(task_id)


@router.post("/{task_id}/render-jobs/{job_id}/cancel", status_code=200)
async def cancel_render_job(
    task_id: Annotated[str, Path()],
    job_id: Annotated[str, Path()],
) -> dict[str, str]:
    """取消正在进行的渲染任务。"""
    task = await mix_repo.get_request(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        cancelled = await job_repo.cancel(job_id)
        if not cancelled:
            raise HTTPException(
                status_code=400,
                detail="Cannot cancel job: not in queued or running state"
            )
        # 更新 mix 的 render_status
        await mix_repo.update_status(task_id, render_status="cancelled")
        return {"message": "Render job cancelled", "job_id": job_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{task_id}/logs", response_model=TaskLogsResponse)
async def get_task_logs(task_id: Annotated[str, Path()]) -> TaskLogsResponse:
    """获取任务日志。"""
    task = await mix_repo.get_request(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # 从任务的 audit_log 和 error_codes 构建日志
    logs: list[LogEntry] = []

    # 添加错误日志
    if task.error_codes:
        for code, details in task.error_codes.items():
            logs.append(
                LogEntry(
                    timestamp=task.updated_at or datetime.utcnow(),
                    level="ERROR",
                    message=f"Error: {code}",
                    details={"error_details": details} if isinstance(details, dict) else {"error": details},
                )
            )

    # 添加渲染任务日志
    render_jobs = await job_repo.list_by_mix(task_id)
    for job in render_jobs:
        if job.error_log:
            logs.append(
                LogEntry(
                    timestamp=job.finished_at or job.submitted_at or datetime.utcnow(),
                    level="ERROR",
                    message=f"Render job {job.id} failed",
                    details={"error_log": job.error_log},
                )
            )
        if job.job_status == "completed":
            logs.append(
                LogEntry(
                    timestamp=job.finished_at or datetime.utcnow(),
                    level="INFO",
                    message=f"Render job {job.id} completed",
                    details=job.metrics,
                )
            )

    # 按时间排序
    logs.sort(key=lambda x: x.timestamp, reverse=True)

    return TaskLogsResponse(task_id=task_id, logs=logs)

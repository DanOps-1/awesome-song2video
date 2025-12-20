"""RenderJob 数据访问。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.domain.models.render_job import RenderJob
from src.infra.persistence.database import get_session


class RenderJobRepository:
    async def save(self, job: RenderJob) -> RenderJob:
        async with get_session() as session:
            merged = await session.merge(job)
            await session.commit()
            await session.refresh(merged)
            return merged

    async def get(self, job_id: str) -> RenderJob | None:
        async with get_session() as session:
            return await session.get(RenderJob, job_id)

    async def mark_success(
        self, job_id: str, *, output_asset_id: str, metrics: dict[str, Any] | None = None
    ) -> None:
        """标记渲染任务成功。

        Args:
            job_id: 任务 ID
            output_asset_id: 输出资源 ID
            metrics: 渲染指标(包含 render 子键)
        """
        async with get_session() as session:
            job = await session.get(RenderJob, job_id)
            if job is None:
                raise ValueError("render job not found")
            job.job_status = "success"
            job.output_asset_id = output_asset_id
            job.finished_at = datetime.utcnow()
            if metrics is not None:
                existing = dict(job.metrics or {})
                existing.update(metrics)
                job.metrics = existing
            await session.commit()

    async def update_status(
        self, job_id: str, *, status: str, metrics: dict[str, Any] | None = None
    ) -> None:
        """更新渲染任务状态和指标。

        支持在任务运行过程中保存指标,如 queued_at/finished_at。

        Args:
            job_id: 任务 ID
            status: 新状态
            metrics: 指标数据(包含 render 子键)
        """
        async with get_session() as session:
            job = await session.get(RenderJob, job_id)
            if job is None:
                raise ValueError("render job not found")
            job.job_status = status
            if status == "running" and job.finished_at is None:
                job.finished_at = None
            elif status in ("success", "failed"):
                job.finished_at = datetime.utcnow()
            if metrics is not None:
                existing = dict(job.metrics or {})
                existing.update(metrics)
                job.metrics = existing
            await session.commit()

    async def mark_failure(self, job_id: str, *, error_log: str) -> None:
        async with get_session() as session:
            job = await session.get(RenderJob, job_id)
            if job is None:
                raise ValueError("render job not found")
            job.job_status = "failed"
            job.error_log = error_log
            job.finished_at = datetime.utcnow()
            await session.commit()

    async def list_by_mix(self, mix_id: str) -> list[RenderJob]:
        """获取指定混剪任务的所有渲染任务。"""
        from sqlmodel import select

        async with get_session() as session:
            stmt = (
                select(RenderJob)
                .where(RenderJob.mix_request_id == mix_id)
                .order_by(RenderJob.submitted_at.desc())  # type: ignore[union-attr]
            )
            result = await session.exec(stmt)
            return list(result)

    async def list_all(self) -> list[RenderJob]:
        """获取所有渲染任务。"""
        from sqlmodel import select

        async with get_session() as session:
            stmt = select(RenderJob).order_by(RenderJob.submitted_at.desc())  # type: ignore[union-attr]
            result = await session.exec(stmt)
            return list(result)

    async def update_progress(self, job_id: str, progress: float) -> None:
        """更新渲染任务进度。

        Args:
            job_id: 任务 ID
            progress: 进度值 (0.0-100.0)
        """
        async with get_session() as session:
            job = await session.get(RenderJob, job_id)
            if job is None:
                raise ValueError("render job not found")
            job.progress = min(100.0, max(0.0, progress))
            await session.commit()

    async def cancel(self, job_id: str) -> bool:
        """取消渲染任务。

        Args:
            job_id: 任务 ID

        Returns:
            是否成功取消（只有 queued 或 running 状态的任务可以取消）
        """
        async with get_session() as session:
            job = await session.get(RenderJob, job_id)
            if job is None:
                raise ValueError("render job not found")
            if job.job_status not in ("queued", "running"):
                return False
            job.job_status = "cancelled"
            job.error_log = "Cancelled by user"
            job.finished_at = datetime.utcnow()
            await session.commit()
            return True

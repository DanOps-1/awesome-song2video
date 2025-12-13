from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import uuid4

from arq.connections import create_pool
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from src.domain.models.render_job import RenderJob
from src.infra.config.settings import get_settings
from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.workers import redis_settings
from src.workers.render_worker import render_mix


router = APIRouter(prefix="/api/v1/mixes/{mix_id}/render", tags=["render"])
repo = RenderJobRepository()
mix_repo = SongMixRepository()
settings = get_settings()


class RenderOptions(BaseModel):
    resolution: str = "1080p"
    frame_rate: int = 25
    bilingual_subtitle: bool = False  # 是否生成中英双语字幕


class RenderResponse(BaseModel):
    job_id: str
    status: str
    progress: float = 0.0
    output_url: str | None = None


@router.post("", response_model=RenderResponse, status_code=202)
async def submit_render(
    mix_id: Annotated[str, Path()],
    body: RenderOptions,
) -> RenderResponse:
    job = RenderJob(
        id=str(uuid4()),
        mix_request_id=mix_id,
        job_status="queued",
        ffmpeg_script="",
        bilingual_subtitle=body.bilingual_subtitle,
    )
    await repo.save(job)
    # 更新 mix 的 render_status 为 "queued"
    await mix_repo.update_status(mix_id, render_status="queued")
    if settings.enable_async_queue:
        pool = await create_pool(redis_settings())
        await pool.enqueue_job("render_mix", job.id)
    else:
        # 在后台运行渲染任务，不阻塞 API 响应
        asyncio.create_task(render_mix({}, job.id))
    return RenderResponse(job_id=job.id, status=job.job_status)


@router.get("", response_model=RenderResponse)
async def get_render_status(mix_id: Annotated[str, Path()], job_id: str) -> RenderResponse:
    job = await repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="render job not found")

    # 如果渲染成功，生成视频下载 URL
    output_url = None
    if job.job_status == "success" and job.output_asset_id:
        # output_asset_id 格式为 "artifacts/renders/{job_id}.mp4"
        # 转换为 URL 路径 "/api/v1/renders/{job_id}.mp4"
        from pathlib import Path

        asset_path = Path(job.output_asset_id)
        output_url = f"/api/v1/renders/{asset_path.name}"

    return RenderResponse(
        job_id=job.id, status=job.job_status, progress=job.progress, output_url=output_url
    )

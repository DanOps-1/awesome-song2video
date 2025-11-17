from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from arq.connections import create_pool
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from src.domain.models.song_mix import SongMixRequest
from src.infra.config.settings import get_settings
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.workers import redis_settings
from src.workers.timeline_worker import build_timeline


router = APIRouter(prefix="/api/v1/mixes", tags=["mixes"])
repo = SongMixRepository()
settings = get_settings()


class MixCreateRequest(BaseModel):
    song_title: str = Field(..., min_length=1, max_length=128)
    artist: str | None = None
    source_type: str = Field(..., pattern="^(upload|catalog)$")
    audio_asset_id: str | None = None
    lyrics_text: str | None = None
    language: str = "zh"
    auto_generate: bool = True


class MixResponse(BaseModel):
    id: str
    song_title: str
    timeline_status: str
    render_status: str


@router.post("", status_code=201, response_model=MixResponse)
async def create_mix(payload: MixCreateRequest) -> MixResponse:
    if not payload.audio_asset_id and not payload.lyrics_text:
        raise HTTPException(status_code=400, detail="必须提供音频或歌词")

    mix = SongMixRequest(
        id=str(uuid4()),
        song_title=payload.song_title,
        artist=payload.artist,
        source_type=payload.source_type,
        audio_asset_id=payload.audio_asset_id,
        lyrics_text=payload.lyrics_text or "",
        language=payload.language,
        owner_id="system",
    )
    saved = await repo.create_request(mix)
    return MixResponse(
        id=saved.id,
        song_title=saved.song_title,
        timeline_status=saved.timeline_status,
        render_status=saved.render_status,
    )


@router.post("/{mix_id}/generate-timeline", status_code=202)
async def trigger_generation(
    mix_id: Annotated[str, Path(description="混剪任务 ID")]
) -> dict[str, str]:
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    trace_id = str(uuid4())
    if settings.enable_async_queue:
        pool = await create_pool(redis_settings())
        await pool.enqueue_job("build_timeline", mix_id)
    else:
        await build_timeline({}, mix_id)

    return {"trace_id": trace_id, "message": "已进入匹配队列"}

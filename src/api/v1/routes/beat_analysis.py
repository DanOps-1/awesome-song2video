"""节拍分析 API 路由。"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel, Field

from src.domain.models.beat_sync import BeatAnalysisData
from src.infra.config.settings import get_settings
from src.infra.persistence.database import get_session
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/mixes", tags=["beat-analysis"])
repo = SongMixRepository()
settings = get_settings()


class BeatAnalysisResponse(BaseModel):
    """节拍分析结果响应。"""

    id: str
    mix_request_id: str
    bpm: float
    beat_count: int
    downbeat_count: int
    tempo_stability: float
    enabled: bool


class BeatSyncToggleRequest(BaseModel):
    """卡点功能开关请求。"""

    enabled: bool = Field(..., description="是否启用卡点功能")


class BeatSyncToggleResponse(BaseModel):
    """卡点功能开关响应。"""

    mix_request_id: str
    beat_sync_enabled: bool
    message: str


@router.post(
    "/{mix_id}/analyze-beats",
    response_model=BeatAnalysisResponse,
    summary="分析音频节拍（已废弃）",
    description="本地节拍分析已移除。请使用 TwelveLabs action 模式进行视频匹配。",
    deprecated=True,
)
async def analyze_beats(
    mix_id: Annotated[str, PathParam(description="Mix ID")],
) -> BeatAnalysisResponse:
    """分析音频节拍。

    注意：本地 librosa 节拍检测已移除，该功能不再可用。
    系统现在使用 TwelveLabs action 模式进行视频-音乐对齐。
    """
    raise HTTPException(
        status_code=501,
        detail="Beat analysis is no longer available. The system now uses TwelveLabs action mode for video-music alignment.",
    )


@router.get(
    "/{mix_id}/beats",
    response_model=BeatAnalysisResponse,
    summary="获取节拍分析数据",
    description="获取已分析的节拍数据。",
)
async def get_beats(
    mix_id: Annotated[str, PathParam(description="Mix ID")],
) -> BeatAnalysisResponse:
    """获取节拍分析数据。"""
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="Mix not found")

    async with get_session() as session:
        from sqlmodel import select

        stmt = select(BeatAnalysisData).where(BeatAnalysisData.mix_request_id == mix_id)
        result = await session.execute(stmt)
        beat_data = result.scalar_one_or_none()

        if beat_data is None:
            raise HTTPException(status_code=404, detail="Beat analysis not found")

        return BeatAnalysisResponse(
            id=beat_data.id,
            mix_request_id=mix_id,
            bpm=beat_data.bpm,
            beat_count=len(beat_data.beat_times_ms),
            downbeat_count=len(beat_data.downbeat_times_ms),
            tempo_stability=beat_data.tempo_stability,
            enabled=beat_data.enabled,
        )


@router.patch(
    "/{mix_id}/beat-sync",
    response_model=BeatSyncToggleResponse,
    summary="开关卡点功能",
    description="为指定 Mix 启用或禁用卡点功能。",
)
async def toggle_beat_sync(
    mix_id: Annotated[str, PathParam(description="Mix ID")],
    payload: BeatSyncToggleRequest,
) -> BeatSyncToggleResponse:
    """开关卡点功能。"""
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="Mix not found")

    async with get_session() as session:
        from sqlmodel import select

        stmt = select(BeatAnalysisData).where(BeatAnalysisData.mix_request_id == mix_id)
        result = await session.execute(stmt)
        beat_data = result.scalar_one_or_none()

        if beat_data is None:
            # 如果没有节拍数据，创建一个空的（enabled=False）
            beat_data = BeatAnalysisData(
                id=str(uuid4()),
                mix_request_id=mix_id,
                bpm=0.0,
                beat_times_ms=[],
                downbeat_times_ms=[],
                beat_strength=[],
                tempo_stability=0.0,
                enabled=payload.enabled,
            )
            session.add(beat_data)
        else:
            beat_data.enabled = payload.enabled

        await session.commit()

    action = "enabled" if payload.enabled else "disabled"
    logger.info("beat_sync.toggled", mix_id=mix_id, enabled=payload.enabled)

    return BeatSyncToggleResponse(
        mix_request_id=mix_id,
        beat_sync_enabled=payload.enabled,
        message=f"Beat sync {action} for mix {mix_id}",
    )


def _resolve_audio_path(audio_asset_id: str | None) -> Path | None:
    """从 audio_asset_id 解析出实际的音频文件路径。"""
    if not audio_asset_id:
        return None

    audio_dir = Path(settings.audio_asset_dir)

    # 查找匹配的文件（可能有不同后缀）
    for ext in [".mp3", ".wav", ".flac", ".m4a", ".aac"]:
        audio_file = audio_dir / f"{audio_asset_id}{ext}"
        if audio_file.exists():
            return audio_file

    # 尝试通配符匹配（文件名可能包含时间戳）
    matches = list(audio_dir.glob(f"{audio_asset_id}*"))
    if matches:
        return matches[0]

    return None

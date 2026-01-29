"""配置管理 Admin API。

TwelveLabs-only architecture - simplified config without ML backend switching.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.domain.services.render_config_service import RenderConfigService
from src.infra.config.settings import get_settings


router = APIRouter(prefix="/config", tags=["admin-config"])
settings = get_settings()
render_config_service = RenderConfigService()


class TwelveLabsConfig(BaseModel):
    api_key_set: bool
    index_id: str
    live_enabled: bool
    audio_search_enabled: bool
    transcription_search_enabled: bool


class RenderConfig(BaseModel):
    concurrency_limit: int
    clip_concurrency: int
    per_video_limit: int
    max_retry: int
    retry_backoff_base_ms: int
    metrics_flush_interval_s: int
    placeholder_clip_path: str


class BeatSyncConfig(BaseModel):
    enabled: bool
    max_adjustment_ms: int
    action_weight: float
    beat_weight: float


class SystemConfig(BaseModel):
    environment: str
    twelvelabs: TwelveLabsConfig
    render: RenderConfig
    beat_sync: BeatSyncConfig
    query_rewrite_enabled: bool
    query_rewrite_score_threshold: float
    query_rewrite_max_attempts: int


class ConfigPatchRequest(BaseModel):
    render_concurrency_limit: int | None = Field(default=None, ge=1, le=10)
    render_clip_concurrency: int | None = Field(default=None, ge=1, le=20)
    render_per_video_limit: int | None = Field(default=None, ge=1, le=5)
    render_max_retry: int | None = Field(default=None, ge=0, le=10)
    query_rewrite_enabled: bool | None = None
    beat_sync_enabled: bool | None = None


class TwelveLabsStatusResponse(BaseModel):
    api_key_set: bool
    index_id: str
    live_enabled: bool
    status: str


@router.get("", response_model=SystemConfig)
async def get_config() -> SystemConfig:
    """获取系统配置。"""
    render_cfg = await render_config_service.get_config()

    return SystemConfig(
        environment=settings.environment,
        twelvelabs=TwelveLabsConfig(
            api_key_set=bool(settings.tl_api_key),
            index_id=settings.tl_index_id,
            live_enabled=settings.tl_live_enabled,
            audio_search_enabled=settings.tl_audio_search_enabled,
            transcription_search_enabled=settings.tl_transcription_search_enabled,
        ),
        render=RenderConfig(
            concurrency_limit=settings.render_concurrency_limit,
            clip_concurrency=settings.render_clip_concurrency,
            per_video_limit=render_cfg.per_video_limit,
            max_retry=render_cfg.max_retry,
            retry_backoff_base_ms=render_cfg.retry_backoff_base_ms,
            metrics_flush_interval_s=render_cfg.metrics_flush_interval_s,
            placeholder_clip_path=render_cfg.placeholder_asset_path,
        ),
        beat_sync=BeatSyncConfig(
            enabled=settings.beat_sync_enabled,
            max_adjustment_ms=settings.beat_sync_max_adjustment_ms,
            action_weight=settings.beat_sync_action_weight,
            beat_weight=settings.beat_sync_beat_weight,
        ),
        query_rewrite_enabled=settings.query_rewrite_enabled,
        query_rewrite_score_threshold=settings.query_rewrite_score_threshold,
        query_rewrite_max_attempts=settings.query_rewrite_max_attempts,
    )


@router.patch("", response_model=SystemConfig)
async def patch_config(body: ConfigPatchRequest) -> SystemConfig:
    """更新系统配置。

    注意: 部分配置需要重启服务才能生效。
    """
    # 更新渲染配置
    render_updates: dict[str, Any] = {}
    if body.render_per_video_limit is not None:
        render_updates["per_video_limit"] = body.render_per_video_limit
    if body.render_max_retry is not None:
        render_updates["max_retry"] = body.render_max_retry

    if render_updates:
        await render_config_service.update_config(render_updates)

    # 注意: 其他配置需要修改环境变量或重启服务
    return await get_config()


@router.get("/twelvelabs", response_model=TwelveLabsStatusResponse)
async def get_twelvelabs_status() -> TwelveLabsStatusResponse:
    """获取 TwelveLabs API 状态。"""
    status = "ready" if settings.tl_api_key and settings.tl_live_enabled else "not_configured"
    if settings.tl_api_key and not settings.tl_live_enabled:
        status = "mock_mode"

    return TwelveLabsStatusResponse(
        api_key_set=bool(settings.tl_api_key),
        index_id=settings.tl_index_id,
        live_enabled=settings.tl_live_enabled,
        status=status,
    )

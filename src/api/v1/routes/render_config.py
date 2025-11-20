"""渲染裁剪配置 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.domain.models.render_clip_config import RenderClipConfig
from src.domain.services.render_config_service import RenderConfigService

router = APIRouter(prefix="/render/config", tags=["render-config"])
service = RenderConfigService()


class RenderClipConfigPatch(BaseModel):
    max_parallelism: int | None = Field(default=None, ge=1, le=6)
    per_video_limit: int | None = Field(default=None, ge=1, le=3)
    max_retry: int | None = Field(default=None, ge=0, le=5)
    placeholder_asset_path: str | None = None
    retry_backoff_base_ms: int | None = Field(default=None, ge=100)
    metrics_flush_interval_s: int | None = Field(default=None, ge=1)


class RenderClipConfigResponse(BaseModel):
    max_parallelism: int
    per_video_limit: int
    max_retry: int
    placeholder_asset_path: str
    retry_backoff_base_ms: int
    metrics_flush_interval_s: int

    @classmethod
    def from_model(cls, config: RenderClipConfig) -> "RenderClipConfigResponse":
        return cls(**config.model_dump())


@router.get("", response_model=RenderClipConfigResponse)
async def get_render_config() -> RenderClipConfigResponse:
    config = await service.get_config()
    return RenderClipConfigResponse.from_model(config)


@router.patch("", response_model=RenderClipConfigResponse)
async def patch_render_config(body: RenderClipConfigPatch) -> RenderClipConfigResponse:
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields provided")
    config = await service.update_config(data)
    return RenderClipConfigResponse.from_model(config)

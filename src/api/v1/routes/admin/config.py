"""配置管理 Admin API。"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.domain.services.render_config_service import RenderConfigService
from src.infra.config.settings import get_settings


router = APIRouter(prefix="/config", tags=["admin-config"])
settings = get_settings()
render_config_service = RenderConfigService()


class RetrieverConfig(BaseModel):
    backend: Literal["twelvelabs", "clip", "vlm"]
    twelvelabs: dict[str, Any]
    clip: dict[str, Any]
    vlm: dict[str, Any]


class RenderConfig(BaseModel):
    concurrency_limit: int
    clip_concurrency: int
    per_video_limit: int
    max_retry: int
    retry_backoff_base_ms: int
    metrics_flush_interval_s: int
    placeholder_clip_path: str


class WhisperConfig(BaseModel):
    model_name: str
    no_speech_threshold: float


class SystemConfig(BaseModel):
    environment: str
    retriever: RetrieverConfig
    render: RenderConfig
    whisper: WhisperConfig
    query_rewrite_enabled: bool
    query_rewrite_mandatory: bool


class ConfigPatchRequest(BaseModel):
    retriever_backend: Literal["twelvelabs", "clip", "vlm"] | None = None
    render_concurrency_limit: int | None = Field(default=None, ge=1, le=10)
    render_clip_concurrency: int | None = Field(default=None, ge=1, le=20)
    render_per_video_limit: int | None = Field(default=None, ge=1, le=5)
    render_max_retry: int | None = Field(default=None, ge=0, le=10)
    whisper_no_speech_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    query_rewrite_enabled: bool | None = None
    query_rewrite_mandatory: bool | None = None


class RetrieverStatusResponse(BaseModel):
    current_backend: str
    available_backends: list[str]
    backend_status: dict[str, dict[str, Any]]


class SwitchRetrieverRequest(BaseModel):
    backend: Literal["twelvelabs", "clip", "vlm"]


@router.get("", response_model=SystemConfig)
async def get_config() -> SystemConfig:
    """获取系统配置。"""
    render_cfg = await render_config_service.get_config()

    return SystemConfig(
        environment=settings.environment,
        retriever=RetrieverConfig(
            backend=settings.retriever_backend,
            twelvelabs={
                "api_key_set": bool(settings.tl_api_key),
                "index_id": settings.tl_index_id,
                "live_enabled": settings.tl_live_enabled,
                "audio_search_enabled": settings.tl_audio_search_enabled,
                "transcription_search_enabled": settings.tl_transcription_search_enabled,
            },
            clip={
                "model_name": settings.clip_model_name,
                "device": settings.clip_device or "auto",
            },
            vlm={
                "model": settings.vlm_model,
                "endpoint": settings.vlm_endpoint,
                "api_key_set": bool(settings.vlm_api_key),
            },
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
        whisper=WhisperConfig(
            model_name=settings.whisper_model_name,
            no_speech_threshold=settings.whisper_no_speech_threshold,
        ),
        query_rewrite_enabled=settings.query_rewrite_enabled,
        query_rewrite_mandatory=settings.query_rewrite_mandatory,
    )


@router.patch("", response_model=SystemConfig)
async def patch_config(body: ConfigPatchRequest) -> SystemConfig:
    """更新系统配置。

    注意: 部分配置需要重启服务才能生效。
    """
    # 更新渲染配置
    render_updates = {}
    if body.render_per_video_limit is not None:
        render_updates["per_video_limit"] = body.render_per_video_limit
    if body.render_max_retry is not None:
        render_updates["max_retry"] = body.render_max_retry

    if render_updates:
        await render_config_service.update_config(render_updates)

    # 注意: 其他配置（如 retriever_backend）需要修改环境变量或重启服务
    # 这里返回当前配置状态
    if body.retriever_backend and body.retriever_backend != settings.retriever_backend:
        raise HTTPException(
            status_code=400,
            detail="Changing retriever backend requires service restart. Use /config/retriever/switch endpoint.",
        )

    return await get_config()


@router.get("/retriever", response_model=RetrieverStatusResponse)
async def get_retriever_status() -> RetrieverStatusResponse:
    """获取检索后端状态。"""
    backend_status: dict[str, dict[str, Any]] = {
        "twelvelabs": {
            "available": bool(settings.tl_api_key),
            "reason": "API key configured" if settings.tl_api_key else "API key not set",
        },
        "clip": {
            "available": True,
            "reason": "Local model, always available",
        },
        "vlm": {
            "available": bool(settings.vlm_api_key),
            "reason": "API key configured" if settings.vlm_api_key else "API key not set",
        },
    }

    return RetrieverStatusResponse(
        current_backend=settings.retriever_backend,
        available_backends=["twelvelabs", "clip", "vlm"],
        backend_status=backend_status,
    )


@router.post("/retriever/switch", status_code=202)
async def switch_retriever(body: SwitchRetrieverRequest) -> dict[str, str]:
    """切换检索后端。

    注意: 此操作需要重启服务才能完全生效。
    """
    if body.backend == settings.retriever_backend:
        return {"message": "Already using this backend", "backend": body.backend}

    # 检查后端是否可用
    if body.backend == "twelvelabs" and not settings.tl_api_key:
        raise HTTPException(status_code=400, detail="TwelveLabs API key not configured")

    if body.backend == "vlm" and not settings.vlm_api_key:
        raise HTTPException(status_code=400, detail="VLM API key not configured")

    # TODO: 实际切换逻辑（需要更新环境变量或配置文件）
    # 目前仅返回提示信息
    return {
        "message": f"Backend switch to '{body.backend}' requested. Please update RETRIEVER_BACKEND environment variable and restart the service.",
        "current_backend": settings.retriever_backend,
        "requested_backend": body.backend,
    }

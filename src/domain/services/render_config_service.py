"""渲染裁剪配置服务。"""

from __future__ import annotations

import json
from typing import Any

import structlog

from src.domain.models.render_clip_config import RenderClipConfig
from src.infra.config.settings import get_settings
from src.infra.messaging.redis_pool import get_redis
from src.workers import render_worker

logger = structlog.get_logger(__name__)

_cached_config: RenderClipConfig | None = None


class RenderConfigService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis = get_redis()

    async def get_config(self) -> RenderClipConfig:
        global _cached_config
        if _cached_config is None:
            _cached_config = RenderClipConfig.from_settings(self._settings)
        return _cached_config

    async def update_config(self, payload: dict[str, Any]) -> RenderClipConfig:
        current = await self.get_config()
        merged = current.model_dump()
        merged.update(payload)
        new_config = RenderClipConfig(**merged)
        await self._broadcast(new_config)
        return new_config

    async def _broadcast(self, config: RenderClipConfig) -> None:
        global _cached_config
        _cached_config = config
        data = json.dumps(config.model_dump())
        try:
            await self._redis.set("render:clip:config", data)
            await self._redis.publish(self._settings.render_config_channel, data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("render_config.broadcast_failed", error=str(exc))
        render_worker.clip_config = config

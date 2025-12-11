"""Redis Pub/Sub 监听，实时更新 RenderClipConfig。"""

from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable

import structlog
from redis.asyncio.client import PubSub

from src.domain.models.render_clip_config import RenderClipConfig
from src.infra.config.settings import get_settings
from src.infra.messaging.redis_pool import get_redis

logger = structlog.get_logger(__name__)


class RenderConfigWatcher:
    def __init__(
        self,
        on_update: Callable[[RenderClipConfig], Awaitable[None]]
        | Callable[[RenderClipConfig], None],
    ) -> None:
        self._channel = get_settings().render_config_channel
        self._on_update = on_update
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._pubsub: PubSub | None = None

    async def start(self) -> None:
        if self._task:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._pubsub:
            await self._pubsub.unsubscribe(self._channel)
            await self._pubsub.close()
        if self._task:
            await self._task
            self._task = None

    async def _run(self) -> None:
        redis = get_redis()
        pubsub = redis.pubsub()
        self._pubsub = pubsub
        await pubsub.subscribe(self._channel)
        logger.info("render_config_watcher.subscribed", channel=self._channel)
        try:
            while not self._stop_event.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    continue
                data = message.get("data")
                if not data:
                    continue
                try:
                    payload = json.loads(data.decode() if isinstance(data, bytes) else data)
                    config = RenderClipConfig(**payload)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("render_config_watcher.invalid_payload", error=str(exc))
                    continue
                await _maybe_await(self._on_update(config))
        finally:
            await pubsub.close()
            logger.info("render_config_watcher.unsubscribed", channel=self._channel)


async def _maybe_await(result: Awaitable[None] | None) -> None:
    if asyncio.iscoroutine(result):
        await result

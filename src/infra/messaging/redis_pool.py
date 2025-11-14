"""Redis 客户端与速率限制工具。"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

import structlog
from redis.asyncio import Redis

from src.infra.config.settings import get_settings


logger = structlog.get_logger(__name__)
_redis: Redis | None = None
_rate_limit_degraded = False
_fallback_buckets: dict[str, tuple[int, float]] = {}


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=False)
    return _redis


async def token_bucket(key: str, limit: int, interval_seconds: int) -> bool:
    """通过 Lua 脚本实现简单的速率限制；若 Redis 不可用则自动退化为本地内存桶。"""

    global _rate_limit_degraded
    try:
        redis = get_redis()
        consumed = await redis.incr(key)
        if consumed == 1:
            await redis.expire(key, interval_seconds)
        return consumed <= limit
    except Exception as exc:  # noqa: BLE001
        if not _rate_limit_degraded:
            logger.warning("redis.rate_limit_unavailable", error=str(exc))
            _rate_limit_degraded = True
        loop = asyncio.get_running_loop()
        now = loop.time()
        count, window_start = _fallback_buckets.get(key, (0, now))
        if now - window_start >= interval_seconds:
            window_start = now
            count = 0
        count += 1
        _fallback_buckets[key] = (count, window_start)
        return count <= limit


async def with_rate_limit(
    key: str,
    limit: int,
    interval_seconds: int,
    action: Callable[[], Awaitable[Any]],
) -> Any:
    if not await token_bucket(key, limit, interval_seconds):
        await asyncio.sleep(interval_seconds)
    return await action()

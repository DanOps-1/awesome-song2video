"""ARQ Worker 通用配置。"""

from __future__ import annotations

from arq.connections import RedisSettings

from src.infra.config.settings import get_settings


def redis_settings() -> RedisSettings:
    redis_url = get_settings().redis_url
    return RedisSettings.from_dsn(redis_url)


class BaseWorkerSettings:
    redis_settings = redis_settings()
    timezone = "Asia/Shanghai"
    allow_abort_jobs = True

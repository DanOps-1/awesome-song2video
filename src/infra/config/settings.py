"""集中化配置管理。"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["dev", "staging", "prod"] = "dev"
    tl_api_key: str
    tl_index_id: str = "6911aaadd68fb776bc1bd8e7"
    tl_live_enabled: bool = False
    tl_api_base_url: str | None = None
    postgres_dsn: str
    redis_url: str
    media_bucket: str
    minio_endpoint: str
    video_asset_dir: str = "media/video"
    audio_asset_dir: str = "media/audio"
    whisper_model_name: str = "large-v3"
    fallback_video_id: str = "broll"
    enable_async_queue: bool = False
    render_concurrency_limit: int = 3
    otel_endpoint: str = "http://localhost:4317"
    default_locale: str = "zh-CN"


@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings()

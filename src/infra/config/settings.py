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

    # 搜索模态配置
    tl_audio_search_enabled: bool = False  # 是否启用 audio 模态
    tl_transcription_search_enabled: bool = (
        False  # 是否启用 transcription 模态（仅 Marengo 3.0 索引支持）
    )

    # 高级搜索选项（Marengo 3.0）
    tl_transcription_mode: Literal["lexical", "semantic", "both"] = (
        "semantic"  # transcription 搜索模式
    )
    tl_search_operator: Literal["or", "and"] = "or"  # 多模态组合方式
    tl_confidence_threshold: float = 0.0  # 置信度阈值 (0.0-1.0)
    postgres_dsn: str
    redis_url: str
    media_bucket: str = "lyrics-mix-media"
    minio_endpoint: str = "localhost:9000"
    video_asset_dir: str = "media/video"
    audio_asset_dir: str = "media/audio"
    fallback_video_id: str = "broll"
    enable_async_queue: bool = False
    render_concurrency_limit: int = 3
    render_clip_concurrency: int = 10
    render_config_channel: str = "render:config"
    render_per_video_limit: int = 2
    render_max_retry: int = 2
    render_retry_backoff_base_ms: int = 500
    render_metrics_flush_interval_s: int = 5
    placeholder_clip_path: str = "media/fallback/clip_placeholder.mp4"
    otel_endpoint: str = "http://localhost:4317"
    default_locale: str = "zh-CN"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    query_rewrite_enabled: bool = True
    query_rewrite_mandatory: bool = False  # 已废弃，使用 score_threshold 替代
    query_rewrite_max_attempts: int = 5  # 最多尝试改写次数（增加到5次以追求更高分数）
    query_rewrite_score_threshold: float = 1.0  # 分数必须达到 1.0，否则持续改写

    # 节拍卡点功能配置 (TwelveLabs action mode only)
    beat_sync_enabled: bool = True
    beat_sync_max_adjustment_ms: int = 500
    beat_sync_action_weight: float = 0.6
    beat_sync_beat_weight: float = 0.4
    beat_sync_use_twelvelabs_highlights: bool = True
    beat_sync_fallback_scene_detection: bool = True
    beat_sync_scene_threshold: float = 0.3

    # 视频片头片尾过滤配置
    video_intro_skip_ms: int = 12000  # 跳过视频开头的毫秒数（卡通片头约 10-15 秒）
    video_outro_skip_ms: int = (
        8000  # 跳过视频结尾的毫秒数（过滤片尾 Credits 如 "Produced by Chuck Jones"）
    )

    # 候选片段最低分数阈值（低于此分数的片段将被过滤）
    candidate_min_score: float = 0.5  # 过滤掉分数过低的候选，提高到 0.5


@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings()  # type: ignore[call-arg]


# 便捷别名
settings = get_settings()

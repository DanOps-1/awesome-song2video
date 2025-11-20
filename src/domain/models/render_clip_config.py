"""Render clip 并发与回退配置模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.infra.config.settings import AppSettings


class RenderClipConfig(BaseModel):
    """描述渲染阶段 clip 裁剪的运行参数。"""

    max_parallelism: int = Field(..., ge=1, le=6)
    per_video_limit: int = Field(..., ge=1, le=3)
    max_retry: int = Field(..., ge=0, le=5)
    placeholder_asset_path: str
    retry_backoff_base_ms: int = Field(..., ge=100)
    metrics_flush_interval_s: int = Field(..., ge=1)

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "RenderClipConfig":
        """根据全局配置构造默认值。"""

        return cls(
            max_parallelism=settings.render_clip_concurrency,
            per_video_limit=settings.render_per_video_limit,
            max_retry=settings.render_max_retry,
            placeholder_asset_path=settings.placeholder_clip_path,
            retry_backoff_base_ms=settings.render_retry_backoff_base_ms,
            metrics_flush_interval_s=settings.render_metrics_flush_interval_s,
        )

    def to_publish_payload(self) -> dict[str, int | str]:
        """用于 Redis Pub/Sub 广播的 payload。"""

        return self.model_dump()

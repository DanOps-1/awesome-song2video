"""指标数据类型定义。

定义 Preview 和 Render 阶段的指标结构,用于:
1. 写入 SongMixRequest.metrics.preview
2. 写入 RenderJob.metrics.render
3. 在 API 响应中序列化
4. 推送到 OTEL/Prometheus
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class PreviewMetrics(TypedDict):
    """Preview manifest 生成后的指标。

    字段说明:
    - line_count: 歌词行数
    - total_duration_ms: 混剪总时长(毫秒)
    - avg_delta_ms: 歌词时间与视频片段的平均对齐偏差(毫秒)
    - max_delta_ms: 最大对齐偏差(毫秒)
    - fallback_count: 使用 fallback 视频的歌词行数
    - generated_at: 生成时间(ISO 8601)
    """

    line_count: int
    total_duration_ms: int
    avg_delta_ms: float
    max_delta_ms: float
    fallback_count: int
    generated_at: str  # ISO 8601 format


class RenderMetrics(TypedDict):
    """Render 完成后的对齐指标。

    字段说明:
    - line_count: 渲染的歌词行数
    - avg_delta_ms: 渲染后的平均对齐偏差(毫秒)
    - max_delta_ms: 渲染后的最大对齐偏差(毫秒)
    - total_duration_ms: 输出视频总时长(毫秒)
    - queued_at: 任务进入队列时间(ISO 8601)
    - finished_at: 任务完成时间(ISO 8601)
    """

    line_count: int
    avg_delta_ms: float
    max_delta_ms: float
    total_duration_ms: int
    queued_at: str  # ISO 8601 format
    finished_at: str  # ISO 8601 format


def create_preview_metrics(
    line_count: int,
    total_duration_ms: int,
    avg_delta_ms: float,
    max_delta_ms: float,
    fallback_count: int,
) -> PreviewMetrics:
    """创建 PreviewMetrics 实例。

    Args:
        line_count: 歌词行数
        total_duration_ms: 混剪总时长(毫秒)
        avg_delta_ms: 平均对齐偏差(毫秒)
        max_delta_ms: 最大对齐偏差(毫秒)
        fallback_count: fallback 行数

    Returns:
        PreviewMetrics 字典
    """
    return PreviewMetrics(
        line_count=line_count,
        total_duration_ms=total_duration_ms,
        avg_delta_ms=avg_delta_ms,
        max_delta_ms=max_delta_ms,
        fallback_count=fallback_count,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )


def create_render_metrics(
    line_count: int,
    avg_delta_ms: float,
    max_delta_ms: float,
    total_duration_ms: int,
    queued_at: datetime,
    finished_at: datetime,
) -> RenderMetrics:
    """创建 RenderMetrics 实例。

    Args:
        line_count: 渲染的歌词行数
        avg_delta_ms: 平均对齐偏差(毫秒)
        max_delta_ms: 最大对齐偏差(毫秒)
        total_duration_ms: 输出视频总时长(毫秒)
        queued_at: 任务进入队列时间
        finished_at: 任务完成时间

    Returns:
        RenderMetrics 字典
    """
    return RenderMetrics(
        line_count=line_count,
        avg_delta_ms=avg_delta_ms,
        max_delta_ms=max_delta_ms,
        total_duration_ms=total_duration_ms,
        queued_at=queued_at.isoformat() + "Z",
        finished_at=finished_at.isoformat() + "Z",
    )

"""Preview 和 Render 指标的 OpenTelemetry 封装。

提供统一的 OTEL Gauge/Counter helper,用于推送 preview/render 指标到 Prometheus。
"""

from __future__ import annotations

from typing import Any

from opentelemetry import metrics
from opentelemetry.metrics import Meter

# 获取全局 meter
meter: Meter = metrics.get_meter("lyrics_mix.preview_render")

# Preview 指标
preview_avg_delta_gauge = meter.create_gauge(
    name="lyrics_preview_avg_delta_ms",
    description="Preview manifest 中歌词与视频片段的平均对齐偏差(毫秒)",
    unit="ms",
)

preview_max_delta_gauge = meter.create_gauge(
    name="lyrics_preview_max_delta_ms",
    description="Preview manifest 中最大对齐偏差(毫秒)",
    unit="ms",
)

preview_fallback_count_counter = meter.create_counter(
    name="lyrics_preview_fallback_count",
    description="使用 fallback 视频的歌词行数",
    unit="lines",
)

preview_line_count_gauge = meter.create_gauge(
    name="lyrics_preview_line_count",
    description="Preview manifest 中的歌词行总数",
    unit="lines",
)

# Render 指标
render_alignment_avg_delta_gauge = meter.create_gauge(
    name="render_alignment_avg_delta_ms",
    description="渲染完成后的平均对齐偏差(毫秒)",
    unit="ms",
)

render_alignment_max_delta_gauge = meter.create_gauge(
    name="render_alignment_max_delta_ms",
    description="渲染完成后的最大对齐偏差(毫秒)",
    unit="ms",
)

render_total_duration_gauge = meter.create_gauge(
    name="render_total_duration_ms",
    description="渲染任务从队列到完成的总耗时(毫秒)",
    unit="ms",
)

render_queue_depth_gauge = meter.create_gauge(
    name="render_queue_depth",
    description="当前等待渲染的任务数",
    unit="jobs",
)

render_clip_inflight_gauge = meter.create_gauge(
    name="render_clip_inflight",
    description="进行中的剪辑任务数",
    unit="clips",
)

render_clip_failures_total = meter.create_counter(
    name="render_clip_failures_total",
    description="剪辑阶段失败的次数",
    unit="clips",
)

render_clip_duration_histogram = meter.create_histogram(
    name="render_clip_duration_ms",
    description="单个剪辑任务耗时",
    unit="ms",
)

render_clip_placeholder_total = meter.create_counter(
    name="render_clip_placeholder_total",
    description="插入占位片段次数",
    unit="clips",
)


def push_preview_metrics(
    mix_id: str,
    line_count: int,
    avg_delta_ms: float,
    max_delta_ms: float,
    fallback_count: int,
    owner_id: str | None = None,
) -> None:
    """推送 preview manifest 指标到 OTEL。

    Args:
        mix_id: 混剪任务 ID
        line_count: 歌词行数
        avg_delta_ms: 平均对齐偏差(毫秒)
        max_delta_ms: 最大对齐偏差(毫秒)
        fallback_count: fallback 行数
        owner_id: 任务所有者 ID(可选)
    """
    labels: dict[str, Any] = {"mix_id": mix_id}
    if owner_id:
        labels["owner_id"] = owner_id

    preview_line_count_gauge.set(line_count, attributes=labels)
    preview_avg_delta_gauge.set(avg_delta_ms, attributes=labels)
    preview_max_delta_gauge.set(max_delta_ms, attributes=labels)

    if fallback_count > 0:
        preview_fallback_count_counter.add(fallback_count, attributes=labels)


def push_render_metrics(
    job_id: str,
    mix_id: str,
    line_count: int,
    avg_delta_ms: float,
    max_delta_ms: float,
    total_duration_ms: int,
    owner_id: str | None = None,
) -> None:
    """推送 render 完成指标到 OTEL。

    Args:
        job_id: 渲染任务 ID
        mix_id: 混剪任务 ID
        line_count: 渲染的歌词行数
        avg_delta_ms: 平均对齐偏差(毫秒)
        max_delta_ms: 最大对齐偏差(毫秒)
        total_duration_ms: 任务总耗时(毫秒)
        owner_id: 任务所有者 ID(可选)
    """
    labels: dict[str, Any] = {"job_id": job_id, "mix_id": mix_id}
    if owner_id:
        labels["owner_id"] = owner_id

    render_alignment_avg_delta_gauge.set(avg_delta_ms, attributes=labels)
    render_alignment_max_delta_gauge.set(max_delta_ms, attributes=labels)
    render_total_duration_gauge.set(total_duration_ms, attributes=labels)


def update_render_queue_depth(depth: int) -> None:
    """更新渲染队列深度指标。

    Args:
        depth: 当前队列中等待的任务数
    """
    render_queue_depth_gauge.set(depth)


def set_clip_inflight(count: int, *, job_id: str, video_id: str | None = None) -> None:
    labels: dict[str, Any] = {"job_id": job_id}
    if video_id:
        labels["video_id"] = video_id
    render_clip_inflight_gauge.set(count, attributes=labels)


def add_clip_failure(
    job_id: str, *, video_id: str | None = None, reason: str | None = None
) -> None:
    labels: dict[str, Any] = {"job_id": job_id}
    if video_id:
        labels["video_id"] = video_id
    if reason:
        labels["reason"] = reason
    render_clip_failures_total.add(1, attributes=labels)


def observe_clip_duration(duration_ms: float, *, job_id: str, video_id: str | None = None) -> None:
    labels: dict[str, Any] = {"job_id": job_id}
    if video_id:
        labels["video_id"] = video_id
    render_clip_duration_histogram.record(duration_ms, attributes=labels)


def add_placeholder_clip(job_id: str, *, video_id: str | None = None) -> None:
    labels: dict[str, Any] = {"job_id": job_id}
    if video_id:
        labels["video_id"] = video_id
    render_clip_placeholder_total.add(1, attributes=labels)

"""渲染阶段指标与报告助手。"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Iterable


def build_clip_stats(
    *,
    total: int,
    success: int,
    failed: int,
    placeholder: int,
    durations: Iterable[float],
    peak_parallelism: int,
) -> dict[str, float | int | str]:
    values = list(durations)
    avg_duration = sum(values) / len(values) if values else 0.0
    p95 = _percentile(values, 0.95) if values else 0.0
    return {
        "total_tasks": total,
        "success_tasks": success,
        "failed_tasks": failed,
        "placeholder_tasks": placeholder,
        "avg_task_duration_ms": round(avg_duration, 2),
        "p95_task_duration_ms": round(p95, 2),
        "peak_parallelism": peak_parallelism,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * percentile
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1

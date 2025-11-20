from __future__ import annotations

import pytest

from src.infra.observability import preview_render_metrics as metrics


class DummyGauge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, dict]] = []

    def set(self, value: int, attributes: dict | None = None) -> None:
        self.calls.append(("set", value, attributes or {}))


class DummyCounter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def add(self, value: int, attributes: dict | None = None) -> None:
        self.calls.append(("add", attributes or {}))


class DummyHistogram:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict]] = []

    def record(self, value: float, attributes: dict | None = None) -> None:
        self.calls.append((value, attributes or {}))


def test_clip_metric_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    inflight = DummyGauge()
    failures = DummyCounter()
    duration = DummyHistogram()

    monkeypatch.setattr(metrics, "render_clip_inflight_gauge", inflight)
    monkeypatch.setattr(metrics, "render_clip_failures_total", failures)
    monkeypatch.setattr(metrics, "render_clip_duration_histogram", duration)
    placeholder = DummyCounter()
    monkeypatch.setattr(metrics, "render_clip_placeholder_total", placeholder)

    metrics.set_clip_inflight(3, job_id="job-1", video_id="vid-1")
    metrics.add_clip_failure("job-1", video_id="vid-1", reason="timeout")
    metrics.observe_clip_duration(1234.5, job_id="job-1", video_id="vid-1")
    metrics.add_placeholder_clip("job-1", video_id="vid-1")

    assert inflight.calls == [("set", 3, {"job_id": "job-1", "video_id": "vid-1"})]
    assert failures.calls == [("add", {"job_id": "job-1", "video_id": "vid-1", "reason": "timeout"})]
    assert duration.calls == [(1234.5, {"job_id": "job-1", "video_id": "vid-1"})]
    assert placeholder.calls == [("add", {"job_id": "job-1", "video_id": "vid-1"})]

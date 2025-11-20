"""针对 TwelveLabsClient 的 rank / score 兼容逻辑单测。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.services.matching.twelvelabs_client import TwelveLabsClient


def _make_client() -> TwelveLabsClient:
    client = TwelveLabsClient.__new__(TwelveLabsClient)
    client._settings = SimpleNamespace(fallback_video_id="mock-video")  # type: ignore[assignment]
    return client


def test_build_candidate_dict_uses_rank_when_score_missing() -> None:
    client = _make_client()

    result = client._build_candidate_dict(
        video_id="vid-123",
        start_seconds=1.5,
        end_seconds=2.5,
        score=None,
        rank=2,
    )

    assert result["rank"] == 2
    assert result["score"] == pytest.approx(0.5)


def test_build_candidate_dict_prefers_score_over_rank() -> None:
    client = _make_client()

    result = client._build_candidate_dict(
        video_id="vid-123",
        start_seconds=0.0,
        end_seconds=1.0,
        score=0.87,
        rank=1,
    )

    assert result["score"] == pytest.approx(0.87)
    assert result["rank"] == 1


def test_normalize_score_handles_missing_values() -> None:
    assert TwelveLabsClient._normalize_score(None, None) == 0.0
    assert TwelveLabsClient._normalize_score(0.6, None) == pytest.approx(0.6)
    assert TwelveLabsClient._normalize_score(None, 0) == 0.0

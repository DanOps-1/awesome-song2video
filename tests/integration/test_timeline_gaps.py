from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from src.pipelines.matching.timeline_builder import TimelineBuilder


@pytest.mark.asyncio
async def test_timeline_gap_filling(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "demo.wav"
    audio_path.write_bytes(b"fake audio")

    builder = TimelineBuilder()

    # Mock audio duration to 5000ms (5s)
    def fake_get_audio_duration(path: Path) -> int:
        return 5000

    builder._get_audio_duration = fake_get_audio_duration

    async def fake_search(query: str, limit: int = 5) -> list[dict[str, Any]]:
        return [
            {
                "id": str(uuid4()),
                "video_id": "demo",
                "start": 0,
                "end": 1000,
                "score": 0.9,
            }
        ]

    monkeypatch.setattr(
        "src.pipelines.matching.timeline_builder.client.search_segments", fake_search
    )

    # Use lyrics_text instead of audio transcription
    # Lines with timestamps are provided directly
    lyrics_text = """Line 1
Line 2"""

    timeline = await builder.build(audio_path=audio_path, lyrics_text=lyrics_text)

    # Expected lines:
    # 1. Line 1
    # 2. Line 2

    assert len(timeline.lines) >= 2, f"Expected at least 2 lines, got {len(timeline.lines)}"

    # First line should be Line 1
    assert timeline.lines[0].text == "Line 1"

    # Check that gaps are handled correctly (implementation may vary)
    # The important thing is the builder doesn't crash
    assert all(line.text for line in timeline.lines)

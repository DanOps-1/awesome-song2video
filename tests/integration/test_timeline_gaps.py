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

    async def fake_transcribe(path: Path) -> list[dict[str, Any]]:
        return [
            {"text": "Line 1", "start": 0.0, "end": 1.0},
            # Gap: 1.0 - 2.0 (1s) > 0.5s, should trigger gap filling
            {"text": "Line 2", "start": 2.0, "end": 3.0},
            # Tail Gap: 3.0 - 5.0 (2s)
        ]

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
        "src.pipelines.matching.timeline_builder.transcribe_with_timestamps", fake_transcribe
    )
    monkeypatch.setattr(
        "src.pipelines.matching.timeline_builder.client.search_segments", fake_search
    )

    timeline = await builder.build(audio_path=audio_path, lyrics_text=None)

    # Expected lines:
    # 1. Line 1 (0-1s)
    # 2. Gap (1-2s)
    # 3. Line 2 (2-3s)
    # 4. Tail Gap (3-5s)

    assert len(timeline.lines) == 4, f"Expected 4 lines, got {len(timeline.lines)}"

    assert timeline.lines[0].text == "Line 1"
    assert timeline.lines[0].start_ms == 0
    assert timeline.lines[0].end_ms == 1000

    assert timeline.lines[1].text == "(Instrumental)"
    assert timeline.lines[1].start_ms == 1000
    assert timeline.lines[1].end_ms == 2000
    # Check fallback candidate
    assert len(timeline.lines[1].candidates) == 1
    assert timeline.lines[1].candidates[0]["start_time_ms"] == 1000
    assert timeline.lines[1].candidates[0]["end_time_ms"] == 2000

    assert timeline.lines[2].text == "Line 2"
    assert timeline.lines[2].start_ms == 2000
    assert timeline.lines[2].end_ms == 3000

    assert timeline.lines[3].text == "(Outro)"
    assert timeline.lines[3].start_ms == 3000
    assert timeline.lines[3].end_ms == 5000

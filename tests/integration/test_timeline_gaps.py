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

    async def fake_transcribe(
        path: Path, language: str | None = None, prompt: str | None = None
    ) -> list[dict[str, Any]]:
        return [
            {"text": "Line 1", "start": 0.0, "end": 1.0},
            # Gap: 1.0 - 3.5 (2.5s) > 2s threshold, should trigger gap filling
            {"text": "Line 2", "start": 3.5, "end": 4.5},
            # Tail Gap: 4.5 - 5.0 (0.5s) < 1s threshold, won't add Outro
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

    # Expected lines with new gap threshold (> 2000ms triggers Instrumental):
    # 1. Line 1 (0-1s)
    # 2. Gap (1s-3.5s = 2.5s > 2s threshold) -> (Instrumental)
    # 3. Line 2 (3.5-4.5s)
    # Note: Tail gap 4.5s-5s = 0.5s < 1s threshold, so no Outro

    assert len(timeline.lines) == 3, f"Expected 3 lines, got {len(timeline.lines)}"

    assert timeline.lines[0].text == "Line 1"
    assert timeline.lines[0].start_ms == 0
    assert timeline.lines[0].end_ms == 1000

    assert timeline.lines[1].text == "(Instrumental)"
    assert timeline.lines[1].start_ms == 1000
    assert timeline.lines[1].end_ms == 3500

    assert timeline.lines[2].text == "Line 2"
    assert timeline.lines[2].start_ms == 3500
    assert timeline.lines[2].end_ms == 4500

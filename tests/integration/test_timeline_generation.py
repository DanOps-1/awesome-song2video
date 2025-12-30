from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from src.pipelines.matching.timeline_builder import TimelineBuilder


@pytest.mark.asyncio
async def test_timeline_builder_returns_segments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audio_path = tmp_path / "demo.wav"
    audio_path.write_bytes(b"fake audio")

    builder = TimelineBuilder()

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
    lyrics_text = """第一句
第二句"""

    timeline = await builder.build(audio_path=audio_path, lyrics_text=lyrics_text)
    assert len(timeline.lines) == 2
    assert timeline.lines[0].candidates

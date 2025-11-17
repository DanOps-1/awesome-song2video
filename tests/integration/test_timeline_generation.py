from pathlib import Path
from uuid import uuid4

import pytest

from src.pipelines.matching.timeline_builder import TimelineBuilder


@pytest.mark.asyncio
async def test_timeline_builder_returns_segments(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    audio_path = tmp_path / "demo.wav"
    audio_path.write_bytes(b"fake audio")

    builder = TimelineBuilder()

    async def fake_transcribe(path: Path):  # type: ignore[override]
        return [
            {"text": "第一句", "start": 0.0, "end": 1.0},
            {"text": "第二句", "start": 1.0, "end": 2.0},
        ]

    async def fake_search(query: str, limit: int = 5):
        return [
            {
                "id": str(uuid4()),
                "video_id": "demo",
                "start": 0,
                "end": 1000,
                "score": 0.9,
            }
        ]

    monkeypatch.setattr("src.pipelines.matching.timeline_builder.transcribe_with_timestamps", fake_transcribe)
    monkeypatch.setattr("src.pipelines.matching.timeline_builder.client.search_segments", fake_search)

    timeline = await builder.build(audio_path=audio_path, lyrics_text=None)
    assert len(timeline.lines) == 2
    assert timeline.lines[0].candidates

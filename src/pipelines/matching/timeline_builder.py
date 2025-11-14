"""构建歌词与视频片段的时间线。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import structlog

from src.infra.config.settings import get_settings
from src.pipelines.lyrics_ingest.transcriber import transcribe_with_timestamps
from src.services.matching.twelvelabs_client import client


@dataclass
class TimelineLine:
    text: str
    start_ms: int
    end_ms: int
    candidates: list[dict]


@dataclass
class TimelineResult:
    lines: list[TimelineLine] = field(default_factory=list)


class TimelineBuilder:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._use_mock_segments = not self._settings.tl_live_enabled
        self._candidate_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._logger = structlog.get_logger(__name__)

    async def build(self, audio_path: Path | None, lyrics_text: Optional[str]) -> TimelineResult:
        self._candidate_cache.clear()
        segments = []
        if audio_path:
            segments = await transcribe_with_timestamps(audio_path)
        elif lyrics_text:
            for idx, line in enumerate(lyrics_text.splitlines()):
                stripped = line.strip()
                if not stripped:
                    continue
                segments.append({"text": stripped, "start": float(idx), "end": float(idx + 1)})
        else:
            raise ValueError("必须提供音频或歌词")

        timeline = TimelineResult()
        for seg in segments:
            raw_text: str = seg["text"]
            text = raw_text.strip().strip("'\"")
            if not text:
                continue
            start_ms = int(float(seg.get("start", 0)) * 1000)
            end_ms = int(float(seg.get("end", start_ms / 1000 + 1)) * 1000)
            candidates = await self._get_candidates(text, limit=3)
            normalized = self._normalize_candidates(candidates, start_ms, end_ms)
            timeline.lines.append(
                TimelineLine(
                    text=text,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    candidates=normalized,
                )
            )
        return timeline

    def _normalize_candidates(
        self, raw_candidates: list[dict[str, int | float | str]], start_ms: int, end_ms: int
    ) -> list[dict[str, int | float | str]]:
        def _candidate_defaults(candidate: dict[str, int | float | str]) -> dict[str, int | float | str]:
            start = int(candidate.get("start", start_ms))
            end = int(candidate.get("end", end_ms))
            if self._use_mock_segments:
                start = start_ms
                end = end_ms
            return {
                "id": str(uuid4()),
                "source_video_id": candidate.get("video_id", self._settings.fallback_video_id),
                "start_time_ms": start,
                "end_time_ms": end,
                "score": candidate.get("score", 0.0),
            }

        if raw_candidates:
            return [_candidate_defaults(c) for c in raw_candidates]
        return [
            {
                "id": str(uuid4()),
                "source_video_id": self._settings.fallback_video_id,
                "start_time_ms": start_ms,
                "end_time_ms": end_ms,
                "score": 0.0,
            }
        ]

    async def _get_candidates(self, text: str, limit: int) -> list[dict[str, Any]]:
        key = (text, limit)
        if key not in self._candidate_cache:
            self._candidate_cache[key] = await client.search_segments(text, limit=limit)
        candidates = [candidate.copy() for candidate in self._candidate_cache[key]]
        count = len(candidates)
        log_method = self._logger.warning if count == 0 else self._logger.info
        log_method(
            "timeline_builder.candidates",
            text_preview=text[:30],
            count=count,
            use_mock=self._use_mock_segments,
        )
        return candidates

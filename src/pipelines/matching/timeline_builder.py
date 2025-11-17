"""构建歌词与视频片段的时间线。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import re
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
        self._split_pattern = re.compile(r"(?:\r?\n)+|[，,。！？!?；;…]")

    async def build(self, audio_path: Path | None, lyrics_text: Optional[str]) -> TimelineResult:
        self._candidate_cache.clear()
        segments: list[dict[str, Any]] = []
        if audio_path:
            raw_segments = await transcribe_with_timestamps(audio_path)
            segments = [dict(segment) for segment in raw_segments]
        elif lyrics_text:
            for idx, line in enumerate(lyrics_text.splitlines()):
                stripped = line.strip()
                if not stripped:
                    continue
                segments.append({"text": stripped, "start": float(idx), "end": float(idx + 1)})
        else:
            raise ValueError("必须提供音频或歌词")

        segments = self._explode_segments(segments)

        timeline = TimelineResult()
        for seg in segments:
            raw_text = str(seg.get("text", ""))
            text = raw_text.strip().strip("'\"")
            if not text:
                continue
            start_value = seg.get("start", 0)
            end_value = seg.get("end")
            start_ms = int(float(start_value) * 1000)
            if end_value is None:
                end_ms = start_ms + 1000
            else:
                end_ms = int(float(end_value) * 1000)
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

    def _explode_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        exploded: list[dict[str, Any]] = []
        for seg in segments:
            text = str(seg.get("text", "")).strip()
            if not text:
                continue
            pieces = [piece.strip() for piece in self._split_pattern.split(text) if piece and piece.strip()]
            if len(pieces) <= 1:
                exploded.append(seg)
                continue
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", start + 1.0))
            if end <= start:
                end = start + 1.0
            duration = end - start
            total_chars = sum(len(piece) for piece in pieces) or len(pieces)
            cursor = start
            for idx, piece in enumerate(pieces):
                ratio = len(piece) / total_chars if total_chars else 1.0 / len(pieces)
                chunk_duration = duration * ratio
                chunk_end = end if idx == len(pieces) - 1 else cursor + chunk_duration
                exploded.append(
                    {
                        **seg,
                        "text": piece,
                        "start": cursor,
                        "end": chunk_end,
                    }
                )
                cursor = chunk_end
        return exploded

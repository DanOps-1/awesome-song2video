"""人工校对与替换片段的业务服务。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.domain.models.song_mix import LyricLine, VideoSegmentMatch
from src.infra.persistence.repositories.line_audit_repository import LineAuditRepository
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.services.matching.twelvelabs_client import client


timeline_repo = SongMixRepository()
audit_repo = LineAuditRepository()


class TimelineEditor:
    async def list_lines(
        self, mix_id: str, min_confidence: float | None = None
    ) -> list[dict[str, Any]]:
        lines = await timeline_repo.list_lines(mix_id)
        items: list[dict[str, Any]] = []
        for line in lines:
            if (
                min_confidence is not None
                and line.auto_confidence
                and line.auto_confidence < min_confidence
            ):
                continue
            items.append(self._serialize_line(line))
        return items

    async def get_line(self, line_id: str) -> dict[str, Any] | None:
        """获取单个歌词行（含候选片段）。"""
        line = await timeline_repo.get_line(line_id)
        if line is None:
            return None
        return self._serialize_line(line)

    async def lock_line(
        self,
        line_id: str,
        *,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
        selected_segment_id: str | None = None,
        annotations: str | None = None,
    ) -> dict[str, Any]:
        line = await timeline_repo.get_line(line_id)
        if line is None:
            raise ValueError("Lyric line not found")

        if start_time_ms is not None:
            line.start_time_ms = start_time_ms
        if end_time_ms is not None:
            line.end_time_ms = end_time_ms
        if selected_segment_id is not None:
            line.selected_segment_id = selected_segment_id
        if annotations is not None:
            line.annotations = annotations
        line.status = "locked"

        updated = await timeline_repo.save_line(line)
        await audit_repo.append_entry(
            line_id,
            {
                "action": "lock",
                "selected_segment_id": selected_segment_id,
                "annotations": annotations,
            },
        )
        return self._serialize_line(updated)

    async def rerun_search(
        self, line_id: str, prompt_override: str | None = None
    ) -> list[dict[str, Any]]:
        line = await timeline_repo.get_line(line_id)
        if line is None:
            raise ValueError("Lyric line not found")
        from src.infra.config.settings import get_settings

        settings = get_settings()
        query = prompt_override or line.original_text
        results = await client.search_segments(query, limit=5)
        candidates: list[VideoSegmentMatch] = []
        serialized: list[dict[str, Any]] = []
        for item in results:
            segment_id = item.get("id", str(uuid4()))
            match = VideoSegmentMatch(
                id=segment_id,
                line_id=line_id,
                source_video_id=item.get("video_id", "unknown"),
                index_id=settings.tl_index_id,
                start_time_ms=int(item.get("start", 0)),
                end_time_ms=int(item.get("end", 0)),
                score=item.get("score", 0.0),
                generated_by="rerank",
                search_query=query,  # 保存用于重新搜索的查询文本
            )
            candidates.append(match)
            serialized.append(
                {
                    "id": match.id,
                    "source_video_id": match.source_video_id,
                    "start_time_ms": match.start_time_ms,
                    "end_time_ms": match.end_time_ms,
                    "score": match.score,
                    "search_query": match.search_query,  # 展示搜索查询文本
                }
            )

        await timeline_repo.replace_candidates(line_id, candidates)
        await audit_repo.append_entry(line_id, {"action": "re-search", "prompt": query})
        return serialized

    def _serialize_line(self, line: LyricLine) -> dict[str, Any]:
        return {
            "id": line.id,
            "line_no": line.line_no,
            "original_text": line.original_text,
            "start_time_ms": line.start_time_ms,
            "end_time_ms": line.end_time_ms,
            "auto_confidence": line.auto_confidence,
            "selected_segment_id": line.selected_segment_id,
            "status": line.status,
            "annotations": line.annotations,
            "audit_log": line.audit_log or [],
            "candidates": [
                {
                    "id": candidate.id,
                    "source_video_id": candidate.source_video_id,
                    "start_time_ms": candidate.start_time_ms,
                    "end_time_ms": candidate.end_time_ms,
                    "score": candidate.score,
                    "search_query": candidate.search_query,  # 展示搜索查询文本
                }
                for candidate in getattr(line, "candidates", [])
            ],
        }

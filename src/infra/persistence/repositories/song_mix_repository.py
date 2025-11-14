"""SongMixRequest 仓储操作。"""

from __future__ import annotations

from typing import Any, Sequence

from collections import defaultdict

from sqlalchemy import delete, select

from src.domain.models.song_mix import LyricLine, SongMixRequest, VideoSegmentMatch
from src.infra.persistence.database import get_session


class SongMixRepository:
    async def create_request(self, mix: SongMixRequest) -> SongMixRequest:
        async with get_session() as session:
            session.add(mix)
            await session.commit()
            await session.refresh(mix)
            return mix

    async def get_request(self, mix_id: str) -> SongMixRequest | None:
        async with get_session() as session:
            return await session.get(SongMixRequest, mix_id)

    async def bulk_insert_lines(self, lines: Sequence[LyricLine]) -> None:
        async with get_session() as session:
            session.add_all(lines)
            await session.commit()

    async def update_timeline_status(self, mix_id: str, status: str) -> None:
        async with get_session() as session:
            mix = await session.get(SongMixRequest, mix_id)
            if mix is None:
                raise ValueError("mix not found")
            mix.timeline_status = status
            await session.commit()

    async def list_lines(self, mix_id: str) -> list[LyricLine]:
        async with get_session() as session:
            result = await session.exec(
                select(LyricLine)
                .where(LyricLine.mix_request_id == mix_id)
                .order_by(LyricLine.line_no)
            )
            rows = result.all()
            lines = [
                row if isinstance(row, LyricLine) else row[0]
                for row in rows
            ]
            if not lines:
                return []
            line_ids = [line.id for line in lines]
            match_result = await session.exec(
                select(VideoSegmentMatch).where(VideoSegmentMatch.line_id.in_(line_ids))
            )
            match_rows = match_result.all()
            matches = [
                row if isinstance(row, VideoSegmentMatch) else row[0]
                for row in match_rows
            ]
            matches_by_line: dict[str, list[VideoSegmentMatch]] = defaultdict(list)
            for match in matches:
                matches_by_line[match.line_id].append(match)
            for line in lines:
                object.__setattr__(line, "candidates", matches_by_line.get(line.id, []))
            return lines

    async def list_lines_with_candidates(self, mix_id: str) -> list[LyricLine]:
        """查询歌词行及其候选片段,用于 preview manifest 构建。

        与 list_lines 功能相同,但语义更明确用于 preview 场景。

        Args:
            mix_id: 混剪任务 ID

        Returns:
            带有 candidates 运行时属性的 LyricLine 列表
        """
        return await self.list_lines(mix_id)

    async def attach_candidates(self, candidates: Sequence[VideoSegmentMatch]) -> None:
        async with get_session() as session:
            session.add_all(candidates)
            await session.commit()

    async def update_preview_metrics(self, mix_id: str, metrics: dict[str, Any]) -> None:
        async with get_session() as session:
            mix = await session.get(SongMixRequest, mix_id)
            if mix is None:
                raise ValueError("mix not found")
            existing = dict(mix.metrics or {})
            existing["preview"] = metrics
            mix.metrics = existing
            await session.commit()

    async def list_locked_lines(self, mix_id: str) -> list[LyricLine]:
        async with get_session() as session:
            result = await session.exec(
                select(LyricLine)
                .where(LyricLine.mix_request_id == mix_id, LyricLine.status == "locked")
                .order_by(LyricLine.line_no)
            )
            rows = result.all()
            lines = [
                row if isinstance(row, LyricLine) else row[0]
                for row in rows
            ]
            line_ids = [line.id for line in lines]
            if not line_ids:
                return []
            match_result = await session.exec(
                select(VideoSegmentMatch).where(VideoSegmentMatch.line_id.in_(line_ids))
            )
            match_rows = match_result.all()
            matches = [
                row if isinstance(row, VideoSegmentMatch) else row[0]
                for row in match_rows
            ]
            matches_by_line: dict[str, list[VideoSegmentMatch]] = defaultdict(list)
            for match in matches:
                matches_by_line[match.line_id].append(match)
            for line in lines:
                object.__setattr__(line, "candidates", matches_by_line.get(line.id, []))
            return lines

    async def replace_candidates(self, line_id: str, candidates: Sequence[VideoSegmentMatch]) -> None:
        async with get_session() as session:
            await session.execute(delete(VideoSegmentMatch).where(VideoSegmentMatch.line_id == line_id))
            session.add_all(candidates)
            await session.commit()

    async def get_line(self, line_id: str) -> LyricLine | None:
        async with get_session() as session:
            return await session.get(LyricLine, line_id)

    async def save_line(self, line: LyricLine) -> LyricLine:
        async with get_session() as session:
            merged = await session.merge(line)
            await session.commit()
            await session.refresh(merged)
            return merged

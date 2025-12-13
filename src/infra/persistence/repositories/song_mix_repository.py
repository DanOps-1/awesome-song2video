"""SongMixRequest 仓储操作。"""

from __future__ import annotations

from typing import Any, Mapping, Sequence, cast

from collections import defaultdict

from sqlalchemy import delete
from sqlmodel import select

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

    async def update_timeline_progress(self, mix_id: str, progress: float) -> None:
        """更新时间线生成进度 (0-100)。"""
        async with get_session() as session:
            mix = await session.get(SongMixRequest, mix_id)
            if mix is None:
                raise ValueError("mix not found")
            mix.timeline_progress = min(100.0, max(0.0, progress))
            await session.commit()

    async def list_lines(self, mix_id: str) -> list[LyricLine]:
        async with get_session() as session:
            stmt = (
                select(LyricLine)
                .where(LyricLine.mix_request_id == mix_id)
                .order_by(cast(Any, LyricLine.line_no))
            )
            result = await session.exec(stmt)
            lines = list(result)
            if not lines:
                return []
            line_ids = [line.id for line in lines]
            match_stmt = select(VideoSegmentMatch).where(
                cast(Any, VideoSegmentMatch.line_id).in_(line_ids)
            )
            match_result = await session.exec(match_stmt)
            matches = list(match_result)
            matches_by_line: dict[str, list[VideoSegmentMatch]] = defaultdict(list)
            for match in matches:
                matches_by_line[match.line_id].append(match)
            for line in lines:
                line.candidates = matches_by_line.get(line.id, [])
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

    async def update_preview_metrics(self, mix_id: str, metrics: Mapping[str, Any]) -> None:
        async with get_session() as session:
            mix = await session.get(SongMixRequest, mix_id)
            if mix is None:
                raise ValueError("mix not found")
            existing = dict(mix.metrics or {})
            existing["preview"] = dict(metrics)
            mix.metrics = existing
            await session.commit()

    async def list_locked_lines(self, mix_id: str) -> list[LyricLine]:
        async with get_session() as session:
            stmt = (
                select(LyricLine)
                .where(LyricLine.mix_request_id == mix_id)
                .where(LyricLine.status == "locked")
                .order_by(cast(Any, LyricLine.line_no))
            )
            result = await session.exec(stmt)
            lines = list(result)
            line_ids = [line.id for line in lines]
            if not line_ids:
                return []
            match_stmt = select(VideoSegmentMatch).where(
                cast(Any, VideoSegmentMatch.line_id).in_(line_ids)
            )
            match_result = await session.exec(match_stmt)
            matches = list(match_result)
            matches_by_line: dict[str, list[VideoSegmentMatch]] = defaultdict(list)
            for match in matches:
                matches_by_line[match.line_id].append(match)
            for line in lines:
                line.candidates = matches_by_line.get(line.id, [])
            return lines

    async def replace_candidates(
        self, line_id: str, candidates: Sequence[VideoSegmentMatch]
    ) -> None:
        async with get_session() as session:
            await session.execute(
                delete(VideoSegmentMatch).where(cast(Any, VideoSegmentMatch.line_id) == line_id)
            )
            session.add_all(candidates)
            await session.commit()

    async def get_line(self, line_id: str) -> LyricLine | None:
        async with get_session() as session:
            line = await session.get(LyricLine, line_id)
            if line is None:
                return None
            # 加载候选片段
            match_stmt = select(VideoSegmentMatch).where(
                cast(Any, VideoSegmentMatch.line_id) == line_id
            )
            match_result = await session.exec(match_stmt)
            line.candidates = list(match_result)
            return line

    async def save_line(self, line: LyricLine) -> LyricLine:
        async with get_session() as session:
            merged = await session.merge(line)
            await session.commit()
            await session.refresh(merged)
            return merged

    async def update_line_text(self, line_id: str, new_text: str) -> LyricLine:
        """更新歌词行的文本内容。"""
        async with get_session() as session:
            line = await session.get(LyricLine, line_id)
            if line is None:
                raise ValueError("line not found")
            line.original_text = new_text
            await session.commit()
            await session.refresh(line)
            return line

    async def lock_line_segment(self, line_id: str, segment_id: str | None) -> LyricLine:
        """锁定歌词行的选中视频片段。

        Args:
            line_id: 歌词行 ID
            segment_id: 选中的视频片段 ID，为 None 时解除锁定

        Returns:
            更新后的歌词行
        """
        async with get_session() as session:
            line = await session.get(LyricLine, line_id)
            if line is None:
                raise ValueError("歌词行不存在")
            line.selected_segment_id = segment_id
            line.status = "locked" if segment_id else "matched"
            await session.commit()
            await session.refresh(line)
            return line

    async def confirm_lyrics(self, mix_id: str) -> None:
        """确认所有歌词，标记 mix 的 lyrics_confirmed 为 True。"""
        async with get_session() as session:
            mix = await session.get(SongMixRequest, mix_id)
            if mix is None:
                raise ValueError("mix not found")
            mix.lyrics_confirmed = True
            await session.commit()

    async def unconfirm_lyrics(self, mix_id: str) -> None:
        """取消确认歌词，返回歌词编辑状态。

        - 重置 lyrics_confirmed 为 False
        - 重置 timeline_status 为 transcribed
        - 清除所有歌词行的视频候选和锁定状态
        """
        async with get_session() as session:
            mix = await session.get(SongMixRequest, mix_id)
            if mix is None:
                raise ValueError("mix not found")

            # 重置状态
            mix.lyrics_confirmed = False
            mix.timeline_status = "transcribed"
            mix.timeline_progress = 0.0

            # 获取所有歌词行
            stmt = select(LyricLine).where(LyricLine.mix_request_id == mix_id)
            result = await session.exec(stmt)
            lines = list(result)
            line_ids = [line.id for line in lines]

            # 清除视频候选
            if line_ids:
                await session.execute(
                    delete(VideoSegmentMatch).where(
                        cast(Any, VideoSegmentMatch.line_id).in_(line_ids)
                    )
                )

            # 重置歌词行状态
            for line in lines:
                line.status = "pending"
                line.selected_segment_id = None

            await session.commit()

    async def list_requests(self) -> list[SongMixRequest]:
        """获取所有混剪任务列表。"""
        async with get_session() as session:
            stmt = select(SongMixRequest).order_by(cast(Any, SongMixRequest.created_at).desc())
            result = await session.exec(stmt)
            return list(result)

    async def update_status(
        self, mix_id: str, *, timeline_status: str | None = None, render_status: str | None = None
    ) -> None:
        """更新任务状态。"""
        async with get_session() as session:
            mix = await session.get(SongMixRequest, mix_id)
            if mix is None:
                raise ValueError("mix not found")
            if timeline_status is not None:
                mix.timeline_status = timeline_status
            if render_status is not None:
                mix.render_status = render_status
            await session.commit()

    async def clear_lyrics(self, mix_id: str) -> int:
        """清理指定任务的所有歌词行和视频匹配数据，用于重新识别。

        Returns:
            删除的歌词行数量
        """
        async with get_session() as session:
            # 先获取歌词行 ID
            stmt = select(LyricLine).where(LyricLine.mix_request_id == mix_id)
            result = await session.exec(stmt)
            lines = list(result)
            line_ids = [line.id for line in lines]

            if line_ids:
                # 删除关联的 VideoSegmentMatch
                await session.execute(
                    delete(VideoSegmentMatch).where(
                        cast(Any, VideoSegmentMatch.line_id).in_(line_ids)
                    )
                )

            # 删除 LyricLine
            await session.execute(
                delete(LyricLine).where(cast(Any, LyricLine.mix_request_id) == mix_id)
            )

            # 重置确认状态
            mix = await session.get(SongMixRequest, mix_id)
            if mix:
                mix.lyrics_confirmed = False

            await session.commit()
            return len(lines)

    async def delete_request(self, mix_id: str) -> None:
        """删除混剪任务及其关联数据。"""
        async with get_session() as session:
            # 先删除关联的 VideoSegmentMatch
            lines = await self.list_lines(mix_id)
            line_ids = [line.id for line in lines]
            if line_ids:
                await session.execute(
                    delete(VideoSegmentMatch).where(
                        cast(Any, VideoSegmentMatch.line_id).in_(line_ids)
                    )
                )
            # 删除 LyricLine
            await session.execute(
                delete(LyricLine).where(cast(Any, LyricLine.mix_request_id) == mix_id)
            )
            # 删除 SongMixRequest
            mix = await session.get(SongMixRequest, mix_id)
            if mix:
                await session.delete(mix)
            await session.commit()

    async def delete_line(self, line_id: str) -> str:
        """删除单个歌词行及其关联的视频匹配。

        Returns:
            被删除行所属的 mix_id
        """
        async with get_session() as session:
            line = await session.get(LyricLine, line_id)
            if line is None:
                raise ValueError("歌词行不存在")

            mix_id = line.mix_request_id
            deleted_line_no = line.line_no

            # 删除关联的 VideoSegmentMatch
            await session.execute(
                delete(VideoSegmentMatch).where(cast(Any, VideoSegmentMatch.line_id) == line_id)
            )

            # 删除歌词行
            await session.delete(line)

            # 重新排序后续行号
            stmt = (
                select(LyricLine)
                .where(LyricLine.mix_request_id == mix_id)
                .where(cast(Any, LyricLine.line_no) > deleted_line_no)
                .order_by(cast(Any, LyricLine.line_no))
            )
            result = await session.exec(stmt)
            for remaining_line in result:
                remaining_line.line_no -= 1

            await session.commit()
            return mix_id

    async def delete_lines_batch(self, line_ids: list[str]) -> tuple[str, int]:
        """批量删除歌词行及其关联的视频匹配。

        Args:
            line_ids: 要删除的歌词行 ID 列表

        Returns:
            (mix_id, 删除数量)
        """
        if not line_ids:
            raise ValueError("请选择要删除的歌词行")

        async with get_session() as session:
            # 获取第一个行以确定 mix_id
            first_line = await session.get(LyricLine, line_ids[0])
            if first_line is None:
                raise ValueError("歌词行不存在")
            mix_id = first_line.mix_request_id

            # 删除关联的 VideoSegmentMatch
            await session.execute(
                delete(VideoSegmentMatch).where(cast(Any, VideoSegmentMatch.line_id).in_(line_ids))
            )

            # 删除歌词行
            await session.execute(delete(LyricLine).where(cast(Any, LyricLine.id).in_(line_ids)))

            # 重新排序所有剩余行号
            stmt = (
                select(LyricLine)
                .where(LyricLine.mix_request_id == mix_id)
                .order_by(cast(Any, LyricLine.start_time_ms))
            )
            result = await session.exec(stmt)
            remaining_lines = list(result)
            for idx, line in enumerate(remaining_lines, start=1):
                line.line_no = idx

            await session.commit()
            return mix_id, len(line_ids)

    async def add_line(
        self,
        mix_id: str,
        text: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> LyricLine:
        """添加新的歌词行，根据时间自动排序到正确位置。

        Args:
            mix_id: 混剪任务 ID
            text: 歌词文本
            start_time_ms: 开始时间（毫秒）
            end_time_ms: 结束时间（毫秒）

        Returns:
            新创建的歌词行
        """
        from uuid import uuid4

        async with get_session() as session:
            # 验证 mix 存在
            mix = await session.get(SongMixRequest, mix_id)
            if mix is None:
                raise ValueError("任务不存在")

            # 获取现有行，按时间排序
            stmt = (
                select(LyricLine)
                .where(LyricLine.mix_request_id == mix_id)
                .order_by(cast(Any, LyricLine.start_time_ms))
            )
            result = await session.exec(stmt)
            existing_lines = list(result)

            # 根据 start_time_ms 找到插入位置
            insert_index = 0
            for i, line in enumerate(existing_lines):
                if line.start_time_ms <= start_time_ms:
                    insert_index = i + 1
                else:
                    break

            # 新行的行号
            new_line_no = insert_index + 1

            # 将插入位置及之后的行号后移
            for line in existing_lines[insert_index:]:
                line.line_no += 1

            # 创建新行
            new_line = LyricLine(
                id=str(uuid4()),
                mix_request_id=mix_id,
                line_no=new_line_no,
                original_text=text,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                status="pending",
            )
            session.add(new_line)
            await session.commit()
            await session.refresh(new_line)
            return new_line

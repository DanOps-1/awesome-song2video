"""时间线预览与性能度量服务。"""

from __future__ import annotations

import statistics
from typing import Any

import structlog

from src.domain.models.metrics import create_preview_metrics
from src.domain.models.song_mix import LyricLine, VideoSegmentMatch
from src.infra.config.settings import get_settings
from src.infra.observability.preview_render_metrics import push_preview_metrics
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository


logger = structlog.get_logger(__name__)


class PreviewService:
    def __init__(self) -> None:
        self._repo = SongMixRepository()
        self._settings = get_settings()

    async def build_manifest(self, mix_id: str, owner_id: str | None = None) -> dict[str, Any]:
        """构建 preview manifest 并计算指标。

        Args:
            mix_id: 混剪任务 ID
            owner_id: 任务所有者 ID (可选,用于 OTEL 标签)

        Returns:
            包含 manifest 和 metrics 的字典
        """
        lines = await self._repo.list_lines_with_candidates(mix_id)
        manifest: list[dict[str, Any]] = []
        deltas: list[float] = []
        total_duration = 0
        fallback_count = 0

        for line in lines:
            segment, is_fallback, fallback_reason = self._select_segment(line)
            entry = {
                "line_id": line.id,
                "line_no": line.line_no,
                "lyrics": line.original_text,
                "source_video_id": segment.source_video_id,
                "clip_start_ms": segment.start_time_ms,
                "clip_end_ms": segment.end_time_ms,
                "confidence": segment.score,
                "fallback": is_fallback,
                "fallback_reason": fallback_reason,
            }
            manifest.append(entry)

            lyric_duration = max(0, line.end_time_ms - line.start_time_ms)
            clip_duration = max(0, segment.end_time_ms - segment.start_time_ms)
            deltas.append(float(abs(lyric_duration - clip_duration)))
            total_duration += lyric_duration

            if is_fallback:
                fallback_count += 1
                logger.warning(
                    "preview.fallback_used",
                    mix_id=mix_id,
                    line_id=line.id,
                    line_no=line.line_no,
                    fallback_reason=fallback_reason,
                )

        # 创建指标
        metrics = create_preview_metrics(
            line_count=len(manifest),
            total_duration_ms=total_duration,
            avg_delta_ms=statistics.mean(deltas) if deltas else 0.0,
            max_delta_ms=float(max(deltas)) if deltas else 0.0,
            fallback_count=fallback_count,
        )

        # 持久化 metrics
        await self._repo.update_preview_metrics(mix_id, metrics)

        # 推送 OTEL 指标
        push_preview_metrics(
            mix_id=mix_id,
            line_count=metrics["line_count"],
            avg_delta_ms=metrics["avg_delta_ms"],
            max_delta_ms=metrics["max_delta_ms"],
            fallback_count=metrics["fallback_count"],
            owner_id=owner_id,
        )

        # 结构化日志
        logger.info(
            "preview.manifest_built",
            mix_id=mix_id,
            line_count=metrics["line_count"],
            avg_delta_ms=metrics["avg_delta_ms"],
            max_delta_ms=metrics["max_delta_ms"],
            fallback_count=metrics["fallback_count"],
            generated_at=metrics["generated_at"],
        )

        return {"manifest": manifest, "metrics": metrics}

    async def get_line_preview(self, mix_id: str, line_id: str) -> dict[str, Any]:
        """获取单行歌词的预览信息。

        Args:
            mix_id: 混剪任务 ID
            line_id: 歌词行 ID

        Returns:
            单行 manifest entry

        Raises:
            ValueError: 行不存在
        """
        lines = await self._repo.list_lines(mix_id)
        for line in lines:
            if line.id == line_id:
                segment, is_fallback, fallback_reason = self._select_segment(line)
                return {
                    "line_id": line.id,
                    "line_no": line.line_no,
                    "lyrics": line.original_text,
                    "source_video_id": segment.source_video_id,
                    "clip_start_ms": segment.start_time_ms,
                    "clip_end_ms": segment.end_time_ms,
                    "confidence": segment.score,
                    "fallback": is_fallback,
                    "fallback_reason": fallback_reason,
                }
        raise ValueError("line not found")

    def _select_segment(self, line: LyricLine) -> tuple[VideoSegmentMatch, bool, str | None]:
        """选择歌词行对应的视频片段。

        优先级:
        1. 用户选中的候选 (selected_segment_id)
        2. 第一个自动候选
        3. Fallback 视频

        Args:
            line: 歌词行

        Returns:
            (segment, is_fallback, fallback_reason) 三元组
        """
        candidates = getattr(line, "candidates", []) or []

        # 优先使用用户选中的候选
        if line.selected_segment_id:
            for match in candidates:
                if match.id == line.selected_segment_id:
                    return (match, False, None)

        # 使用第一个候选
        if candidates:
            return (candidates[0], False, None)

        # Fallback: TwelveLabs 无命中
        fallback_segment = VideoSegmentMatch(
            id="fallback",
            line_id=line.id,
            source_video_id=self._settings.fallback_video_id,
            index_id=self._settings.tl_index_id,
            start_time_ms=line.start_time_ms,
            end_time_ms=line.end_time_ms,
            score=0.0,
            generated_by="fallback",
        )
        return (fallback_segment, True, "no_candidates_from_twelvelabs")


preview_service = PreviewService()

"""TwelveLabs 视频检索器 - 实现统一检索接口"""

from __future__ import annotations

from typing import List, Optional

import structlog

from src.retrieval.protocol import VideoClip
from src.services.matching.twelvelabs_client import TwelveLabsClient
from src.services.matching.query_rewriter import QueryRewriter
from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)


class TwelveLabsRetriever:
    """TwelveLabs 视频检索器

    实现 VideoRetriever 协议，提供：
    - 云端多模态视频搜索
    - 智能查询改写
    - 结果规范化
    """

    def __init__(self) -> None:
        self._client = TwelveLabsClient()
        self._rewriter = QueryRewriter()
        self._settings = get_settings()

    async def search(
        self,
        query: str,
        limit: int = 5,
        duration_hint_ms: Optional[int] = None,
    ) -> List[VideoClip]:
        """搜索视频片段

        Args:
            query: 搜索查询文本（歌词）
            limit: 返回结果数量上限
            duration_hint_ms: 期望时长提示（用于过滤）

        Returns:
            匹配的视频片段列表
        """
        # 检查是否需要改写
        rewrite_enabled = self._settings.query_rewrite_enabled
        rewrite_mandatory = self._settings.query_rewrite_mandatory
        max_attempts = self._settings.query_rewrite_max_attempts

        results = []

        if rewrite_mandatory and rewrite_enabled:
            # 强制改写模式：先改写再搜索
            for attempt in range(max_attempts):
                rewritten = await self._rewriter.rewrite(query, attempt)
                raw_results = await self._client.search_segments(rewritten, limit)
                if raw_results:
                    results = self._convert_results(raw_results, duration_hint_ms)
                    break
        else:
            # 按需改写模式：先用原始查询，失败后再改写
            raw_results = await self._client.search_segments(query, limit)
            if raw_results:
                results = self._convert_results(raw_results, duration_hint_ms)
            elif rewrite_enabled:
                for attempt in range(max_attempts):
                    rewritten = await self._rewriter.rewrite(query, attempt)
                    raw_results = await self._client.search_segments(rewritten, limit)
                    if raw_results:
                        results = self._convert_results(raw_results, duration_hint_ms)
                        break

        logger.info(
            "twelvelabs_retriever.search",
            query=query[:50],
            result_count=len(results),
            duration_hint_ms=duration_hint_ms,
        )

        return results

    async def index_video(self, video_path: str) -> int:
        """索引视频文件

        TwelveLabs 使用云端索引，不支持本地索引。

        Raises:
            NotImplementedError: TwelveLabs 不支持本地索引
        """
        raise NotImplementedError(
            "TwelveLabs uses cloud-based indexing. "
            "Please upload videos through the TwelveLabs dashboard or API."
        )

    def supports_indexing(self) -> bool:
        """是否支持本地索引

        Returns:
            False，TwelveLabs 使用云端索引
        """
        return False

    def _convert_results(
        self,
        raw_results: list[dict],
        duration_hint_ms: Optional[int] = None,
    ) -> List[VideoClip]:
        """转换原始结果为 VideoClip 格式"""
        clips = []

        for item in raw_results:
            clip = VideoClip(
                video_id=item.get("video_id", ""),
                start_ms=item.get("start", 0),
                end_ms=item.get("end", 0),
                score=item.get("score", 0.0),
                metadata={
                    "id": item.get("id"),
                    "rank": item.get("rank"),
                },
            )

            # 如果有时长提示，过滤时长差异过大的结果
            if duration_hint_ms:
                clip_duration = clip.duration_ms
                if clip_duration < duration_hint_ms * 0.3:
                    # 片段太短，跳过
                    continue

            clips.append(clip)

        return clips

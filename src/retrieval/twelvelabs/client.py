"""TwelveLabs SDK 客户端封装

支持多模态搜索、故障转移、结果规范化。
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Any, Iterable, cast
from uuid import uuid4

import structlog
from anyio import to_thread
from twelvelabs import TwelveLabs

from src.infra.config.settings import get_settings
from src.infra.messaging.redis_pool import with_rate_limit

logger = structlog.get_logger(__name__)


@dataclass
class TwelveLabsMatch:
    """TwelveLabs 搜索结果匹配项"""

    id: str
    video_id: str
    start: int  # 毫秒
    end: int  # 毫秒
    score: float
    rank: int | None = None
    preview: str | None = None


class TwelveLabsClient:
    """TwelveLabs SDK 客户端封装

    支持：
    - 多模态搜索（visual, audio, transcription）
    - 故障转移（多 base_url 轮询）
    - 结果规范化和去重
    - Mock 模式（本地测试）
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._live_enabled = self._settings.tl_live_enabled
        self._index_id = self._settings.tl_index_id
        self._client: Any | None = None
        self._base_urls = self._build_base_url_chain()
        self._base_url_index = -1

        # 搜索模态配置
        self._audio_enabled = self._settings.tl_audio_search_enabled
        self._transcription_enabled = self._settings.tl_transcription_search_enabled

        # 高级搜索选项（Marengo 3.0）
        self._transcription_mode = self._settings.tl_transcription_mode
        self._search_operator = self._settings.tl_search_operator
        self._confidence_threshold = self._settings.tl_confidence_threshold

        self._current_base_url: str | None = None
        if self._live_enabled:
            self._advance_client()

    async def search_segments(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """搜索视频片段

        Args:
            query: 搜索查询文本
            limit: 返回结果数量上限

        Returns:
            匹配的视频片段列表
        """
        if not self._live_enabled or self._client is None:
            logger.info("twelvelabs.mock_search", query=query)
            return self._mock_results(query, limit)

        option_chain = self._build_option_chain()
        rate_key = f"tl-search:{self._index_id}"

        async def _run_with_options(options: list[str]) -> list[dict[str, Any]]:
            def blocking_call() -> list[dict[str, Any]]:
                logger.info(
                    "twelvelabs.search_query",
                    query=query,
                    base_url=self._current_base_url,
                    options=options,
                )
                client = cast(Any, self._client)

                search_params: dict[str, Any] = {
                    "index_id": self._index_id,
                    "query_text": query,
                    "search_options": options,
                    "group_by": "clip",
                    "page_limit": max(limit, 10),
                }

                if "transcription" in options:
                    transcription_opts = self._build_transcription_options()
                    if transcription_opts:
                        search_params["transcription_options"] = transcription_opts

                if len(options) > 1:
                    search_params["operator"] = self._search_operator

                if self._confidence_threshold > 0:
                    search_params["adjust_confidence_level"] = self._confidence_threshold

                pager = client.search.query(**search_params)
                return self._convert_results(pager, limit)

            return await to_thread.run_sync(blocking_call)

        for options in option_chain:
            try:

                async def _execute() -> list[dict[str, Any]]:
                    return await _run_with_options(options)

                results = cast(
                    list[dict[str, Any]],
                    await with_rate_limit(
                        rate_key,
                        limit=40,
                        interval_seconds=60,
                        action=_execute,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "twelvelabs.search_failed",
                    error=str(exc),
                    live_enabled=self._live_enabled,
                    base_url=self._current_base_url,
                    options=options,
                )
                if self._live_enabled and self._advance_client():
                    logger.info("twelvelabs.client_failover", base_url=self._current_base_url)
                    continue
                if self._live_enabled:
                    raise RuntimeError("TwelveLabs 搜索请求失败，请检查网络或 API 配置") from exc
                return self._mock_results(query, limit)

            if results:
                return results
            logger.warning(
                "twelvelabs.search_empty",
                query=query,
                options=options,
                base_url=self._current_base_url,
            )

        return []

    def _mock_results(self, query: str, limit: int) -> list[dict[str, Any]]:
        """生成 Mock 搜索结果（用于本地测试）"""
        matches: list[TwelveLabsMatch] = []
        base_id = self._settings.fallback_video_id or "mock"
        for idx in range(limit):
            start = idx * 2000
            matches.append(
                TwelveLabsMatch(
                    id=str(uuid4()),
                    video_id=base_id,
                    start=start,
                    end=start + 1500,
                    score=round(random.uniform(0.6, 0.95), 2),
                    rank=idx + 1,
                )
            )
        return [
            {
                "id": match.id,
                "video_id": match.video_id,
                "start": match.start,
                "end": match.end,
                "score": match.score,
                "rank": match.rank,
            }
            for match in matches
        ]

    def _is_in_intro_zone(self, start_seconds: float) -> bool:
        """检查片段是否在片头区域（应被过滤）"""
        intro_skip_ms = self._settings.video_intro_skip_ms
        if intro_skip_ms <= 0:
            return False
        start_ms = int(start_seconds * 1000)
        return start_ms < intro_skip_ms

    def _convert_results(self, items: Iterable[Any], limit: int) -> list[dict[str, Any]]:
        """转换 API 响应为标准格式"""
        results: list[dict[str, Any]] = []
        seen_videos: set[str] = set()
        intro_filtered_count = 0

        for item in items:
            clips = getattr(item, "clips", None) or []
            if clips:
                for clip in clips:
                    video_id = clip.video_id or item.video_id
                    start = getattr(clip, "start", None)
                    end = getattr(clip, "end", None)

                    if start is None or end is None:
                        continue

                    # 过滤片头区域
                    if self._is_in_intro_zone(start):
                        intro_filtered_count += 1
                        continue

                    if video_id in seen_videos:
                        continue

                    results.append(
                        self._build_candidate_dict(
                            video_id,
                            start,
                            end,
                            getattr(clip, "score", None),
                            getattr(clip, "rank", None),
                        )
                    )
                    seen_videos.add(video_id)

                    if len(results) >= limit:
                        if intro_filtered_count > 0:
                            logger.debug(
                                "twelvelabs.intro_filtered",
                                count=intro_filtered_count,
                                intro_skip_ms=self._settings.video_intro_skip_ms,
                            )
                        return results
            else:
                video_id = getattr(item, "video_id", None)
                start = getattr(item, "start", None)
                end = getattr(item, "end", None)

                if start is None or end is None:
                    continue

                # 过滤片头区域
                if self._is_in_intro_zone(start):
                    intro_filtered_count += 1
                    continue

                if video_id in seen_videos:
                    continue

                results.append(
                    self._build_candidate_dict(
                        video_id,
                        start,
                        end,
                        getattr(item, "score", None),
                        getattr(item, "rank", None),
                    )
                )
                seen_videos.add(video_id)

            if len(results) >= limit:
                break

        if intro_filtered_count > 0:
            logger.debug(
                "twelvelabs.intro_filtered",
                count=intro_filtered_count,
                intro_skip_ms=self._settings.video_intro_skip_ms,
            )

        return results

    def _build_candidate_dict(
        self,
        video_id: str | None,
        start_seconds: float | None,
        end_seconds: float | None,
        score: float | None,
        rank: int | None,
    ) -> dict[str, Any]:
        start_ms = int((start_seconds or 0.0) * 1000)
        end_ms = int((end_seconds or 0.0) * 1000)
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        normalized_score = self._normalize_score(score, rank)
        return {
            "id": str(uuid4()),
            "video_id": video_id or self._settings.fallback_video_id,
            "start": start_ms,
            "end": end_ms,
            "score": normalized_score,
            "rank": rank,
        }

    @staticmethod
    def _normalize_score(score: float | None, rank: int | None) -> float:
        if score is not None:
            try:
                return float(score)
            except (TypeError, ValueError):
                return 0.0
        if rank is not None and rank > 0:
            return round(1.0 / float(rank), 6)
        return 0.0

    def _build_base_url_chain(self) -> list[str | None]:
        urls: list[str | None] = []
        custom = self._settings.tl_api_base_url
        if custom:
            urls.append(custom.rstrip("/"))
        urls.append(None)
        urls.append("https://api.twelvelabs.com/v1.3")
        seen: set[str | None] = set()
        unique: list[str | None] = []
        for url in urls:
            if url not in seen:
                unique.append(url)
                seen.add(url)
        return unique

    def _advance_client(self) -> bool:
        if not self._live_enabled:
            return False
        self._base_url_index += 1
        while self._base_url_index < len(self._base_urls):
            base_url = self._base_urls[self._base_url_index]
            try:
                if base_url:
                    os.environ["TWELVELABS_BASE_URL"] = base_url
                    kwargs: dict[str, Any] = {"base_url": base_url}
                else:
                    os.environ.pop("TWELVELABS_BASE_URL", None)
                    kwargs = {}
                self._client = TwelveLabs(api_key=self._settings.tl_api_key, **kwargs)
                self._current_base_url = base_url or "default"
                logger.info("twelvelabs.client_initialized", base_url=self._current_base_url)
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("twelvelabs.client_init_failed", base_url=base_url, error=str(exc))
                self._base_url_index += 1
        self._client = None
        return False

    def _build_transcription_options(self) -> list[str]:
        if self._transcription_mode == "lexical":
            return ["lexical"]
        elif self._transcription_mode == "semantic":
            return ["semantic"]
        elif self._transcription_mode == "both":
            return ["lexical", "semantic"]
        return []

    def _build_option_chain(self) -> list[list[str]]:
        if not self._audio_enabled and not self._transcription_enabled:
            return [["visual"]]

        enabled_modalities = ["visual"]
        if self._audio_enabled:
            enabled_modalities.append("audio")
        if self._transcription_enabled:
            enabled_modalities.append("transcription")

        return [
            enabled_modalities,
            ["visual"],
        ]


# 全局客户端实例
client = TwelveLabsClient()

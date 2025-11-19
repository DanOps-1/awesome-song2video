"""TwelveLabs SDK 客户端封装（支持本地 mock 与真实调用）。"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Any, Iterable, List, cast
from uuid import uuid4

import structlog
from anyio import to_thread
from twelvelabs import TwelveLabs

from src.infra.config.settings import get_settings
from src.infra.messaging.redis_pool import with_rate_limit

logger = structlog.get_logger(__name__)


@dataclass
class TwelveLabsMatch:
    id: str
    video_id: str
    start: int
    end: int
    score: float
    rank: int | None = None
    preview: str | None = None


class TwelveLabsClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._live_enabled = self._settings.tl_live_enabled
        self._index_id = self._settings.tl_index_id
        self._client: Any | None = None
        self._base_urls = self._build_base_url_chain()
        self._base_url_index = -1
        self._audio_enabled = self._settings.tl_audio_search_enabled
        self._current_base_url: str | None = None
        if self._live_enabled:
            self._advance_client()

    async def search_segments(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self._live_enabled or self._client is None:
            logger.info("twelvelabs.mock_search", query=query)
            return self._mock_results(query, limit)

        option_chain = self._build_option_chain()
        rate_key = f"tl-search:{self._index_id}"

        async def _run_with_options(options: list[str]) -> list[dict[str, Any]]:
            def blocking_call() -> list[dict[str, Any]]:
                logger.info("twelvelabs.search_query", query=query, base_url=self._current_base_url, options=options)
                client = cast(Any, self._client)
                pager = client.search.query(
                    index_id=self._index_id,
                    query_text=query,
                    search_options=options,
                    group_by="clip",
                    page_limit=max(limit, 10),
                )
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
        # 使用 fallback 视频生成伪造片段，方便本地测试
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

    def _convert_results(self, items: Iterable[Any], limit: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in items:
            try:
                logger.info(
                    "twelvelabs.raw_item",
                    video_id=getattr(item, "video_id", None),
                    score=getattr(item, "score", None),
                    rank=getattr(item, "rank", None),
                    clips_count=len(getattr(item, "clips", []) or []),
                )
            except Exception:  # noqa: BLE001
                pass
            clips = getattr(item, "clips", None) or []
            if clips:
                for clip in clips:
                    results.append(
                        self._build_candidate_dict(
                            clip.video_id or item.video_id,
                            clip.start,
                            clip.end,
                            getattr(clip, "score", None),
                            getattr(clip, "rank", None),
                        )
                    )
                    if len(results) >= limit:
                        return results
            else:
                results.append(
                    self._build_candidate_dict(
                        getattr(item, "video_id", None),
                        getattr(item, "start", None),
                        getattr(item, "end", None),
                        getattr(item, "score", None),
                        getattr(item, "rank", None),
                    )
                )
            if len(results) >= limit:
                break
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
            except (TypeError, ValueError):  # noqa: BLE001
                return 0.0
        if rank is not None and rank > 0:
            return round(1.0 / float(rank), 6)
        return 0.0

    def _build_base_url_chain(self) -> list[str | None]:
        urls: list[str | None] = []
        custom = self._settings.tl_api_base_url
        if custom:
            urls.append(custom.rstrip("/"))
        urls.append(None)  # 使用 SDK 默认（https://api.twelvelabs.io/...）
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

    def _build_option_chain(self) -> list[list[str]]:
        if not self._audio_enabled:
            return [["visual"]]
        return [
            ["visual", "audio"],
            ["audio"],
            ["visual"],
        ]


client = TwelveLabsClient()

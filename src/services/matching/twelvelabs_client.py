"""TwelveLabs SDK 客户端封装（支持本地 mock 与真实调用）。"""

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

                # 构建搜索参数
                search_params: dict[str, Any] = {
                    "index_id": self._index_id,
                    "query_text": query,
                    "search_options": options,
                    "group_by": "clip",
                    "page_limit": max(limit, 10),
                }

                # Marengo 3.0 高级参数（仅当索引支持时才有效）
                # transcription_options（仅当使用 transcription 时）
                if "transcription" in options:
                    transcription_opts = self._build_transcription_options()
                    if transcription_opts:
                        search_params["transcription_options"] = transcription_opts

                # operator（多模态组合方式）
                if len(options) > 1:
                    search_params["operator"] = self._search_operator

                # adjust_confidence_level（置信度阈值）
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
        seen_videos: set[str] = set()  # 追踪已使用的 video_id，避免重复

        for item in items:
            try:
                logger.info(
                    "twelvelabs.raw_item",
                    video_id=getattr(item, "video_id", None),
                    score=getattr(item, "score", None),
                    rank=getattr(item, "rank", None),
                    start=getattr(item, "start", None),
                    end=getattr(item, "end", None),
                    clips_count=len(getattr(item, "clips", []) or []),
                )
            except Exception:  # noqa: BLE001
                pass

            clips = getattr(item, "clips", None) or []
            if clips:
                for clip in clips:
                    video_id = clip.video_id or item.video_id
                    start = getattr(clip, "start", None)
                    end = getattr(clip, "end", None)

                    # 跳过时间戳为 null 的结果（无效数据）
                    if start is None or end is None:
                        logger.warning(
                            "twelvelabs.invalid_timestamp",
                            video_id=video_id,
                            rank=getattr(clip, "rank", None),
                            start=start,
                            end=end,
                            message="跳过时间戳为 null 的 clip",
                        )
                        continue

                    # 跳过已使用过的视频
                    if video_id in seen_videos:
                        logger.debug(
                            "twelvelabs.skip_duplicate_video",
                            video_id=video_id,
                            rank=getattr(clip, "rank", None),
                        )
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
                        return results
            else:
                video_id = getattr(item, "video_id", None)
                start = getattr(item, "start", None)
                end = getattr(item, "end", None)

                # 跳过时间戳为 null 的结果（无效数据）
                if start is None or end is None:
                    logger.warning(
                        "twelvelabs.invalid_timestamp",
                        video_id=video_id,
                        rank=getattr(item, "rank", None),
                        start=start,
                        end=end,
                        message="跳过时间戳为 null 的结果",
                    )
                    continue

                # 跳过已使用过的视频
                if video_id in seen_videos:
                    logger.debug(
                        "twelvelabs.skip_duplicate_video",
                        video_id=video_id,
                        rank=getattr(item, "rank", None),
                    )
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

    def _build_transcription_options(self) -> list[str]:
        """构建 transcription_options 参数（仅 Marengo 3.0）。

        返回:
            - ["lexical"] - 关键词精确匹配
            - ["semantic"] - 语义匹配
            - ["lexical", "semantic"] - 两者都用（最广泛）
        """
        if self._transcription_mode == "lexical":
            return ["lexical"]
        elif self._transcription_mode == "semantic":
            return ["semantic"]
        elif self._transcription_mode == "both":
            return ["lexical", "semantic"]
        return []

    def _build_option_chain(self) -> list[list[str]]:
        """构建搜索选项链。

        默认只使用 visual（视觉）模态，这是最安全的选择。

        可用的搜索模态（search_options）：
        - visual: 视觉内容（场景、物体、动作、OCR 文字、品牌标志等）
        - audio: 音频内容（音乐、环境声等，具体范围取决于索引的 Marengo 版本）
        - transcription: 语音转文字（仅 Marengo 3.0 引擎的索引支持）

        重要概念：
        - model_options（索引创建时设置）：决定哪些模态被索引，创建后不可修改
        - search_options（搜索时设置）：决定使用哪些模态搜索，必须是 model_options 的子集

        注意：
        - 如果 search_options 包含索引 model_options 不支持的模态，搜索可能失败
        - 本实现采用降级策略：如果多模态搜索失败，会自动回退到只用 visual

        参考：
        - https://docs.twelvelabs.io/v1.3/docs/concepts/indexes
        - https://docs.twelvelabs.io/v1.3/docs/concepts/modalities
        - https://docs.twelvelabs.io/v1.3/api-reference/any-to-video-search/make-search-request
        """
        # 默认只用 visual
        if not self._audio_enabled and not self._transcription_enabled:
            return [["visual"]]

        # 构建启用的模态列表
        enabled_modalities = ["visual"]
        if self._audio_enabled:
            enabled_modalities.append("audio")
        if self._transcription_enabled:
            enabled_modalities.append("transcription")

        # 返回组合策略：全部模态 -> 仅 visual（降级）
        return [
            enabled_modalities,
            ["visual"],
        ]


client = TwelveLabsClient()

"""查询改写模块：将抽象歌词转换为具体视觉描述。"""

from __future__ import annotations

import structlog
from openai import AsyncOpenAI

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)

# 角色名称关键词（用于验证查询是否包含猫鼠角色）
CHARACTER_KEYWORDS = [
    "cat",
    "mouse",
    "kitten",
    "kitty",
    "feline",
    "rodent",
    "tabby",
    "猫",
    "鼠",
    "老鼠",
]


class QueryRewriter:
    """使用 LLM 将抽象/隐喻的歌词改写为具体的视觉场景描述。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = settings.query_rewrite_enabled
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url
        self._client: AsyncOpenAI | None = None

        if self._enabled and self._api_key:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
            logger.info(
                "query_rewriter.initialized",
                enabled=True,
                base_url=self._base_url,
            )
        else:
            logger.info(
                "query_rewriter.disabled",
                enabled=self._enabled,
                has_api_key=bool(self._api_key),
            )

    def _contains_character(self, query: str) -> bool:
        """检查查询是否包含猫鼠角色关键词"""
        query_lower = query.lower()
        for keyword in CHARACTER_KEYWORDS:
            if keyword in query_lower:
                return True
        return False

    def _ensure_character_in_query(self, query: str) -> str:
        """
        确保查询包含角色名称。

        如果查询不包含任何角色关键词，在前面添加 "cat and mouse"。
        这样可以确保 TwelveLabs 搜索结果更可能包含主角。
        """
        if self._contains_character(query):
            return query

        # 不包含角色名称，添加 "cat and mouse" 前缀
        fixed_query = f"cat and mouse {query}"
        logger.info(
            "query_rewriter.character_added",
            original=query,
            fixed=fixed_query,
            message="查询缺少角色名称，已添加 'cat and mouse' 前缀",
        )
        return fixed_query

    async def rewrite(self, original_query: str, attempt: int = 0) -> str:
        """
        改写查询文本。

        Args:
            original_query: 原始歌词文本
            attempt: 重试次数（0=第一次改写，1=第二次改写...）

        Returns:
            改写后的查询，如果未启用或失败则返回原始文本
        """
        if not self._enabled or not self._client:
            return original_query

        try:
            rewritten = await self._call_llm(original_query, attempt)

            # 🎬 强制角色验证：确保查询包含 cat/mouse 角色
            rewritten = self._ensure_character_in_query(rewritten)

            logger.info(
                "query_rewriter.rewritten",
                original=original_query,
                attempt=attempt,
                rewritten=rewritten,
            )
            return rewritten
        except Exception as e:
            logger.warning(
                "query_rewriter.failed",
                original=original_query,
                attempt=attempt,
                error=str(e),
            )
            # 即使失败，也确保原始查询包含角色名称
            return self._ensure_character_in_query(original_query)

    async def _call_llm(self, query: str, attempt: int = 0) -> str:
        """
        调用 LLM API 进行改写。

        Args:
            query: 原始查询
            attempt: 重试次数，决定使用哪种改写策略
        """
        if not self._client:
            return query

        # 根据尝试次数选择不同的改写策略
        system_prompt = self._get_rewrite_strategy(attempt)

        # 根据尝试次数调整温度，增加多样性
        temperature = 0.3 + (attempt * 0.2)  # 0.3, 0.5, 0.7, 0.9...
        temperature = min(temperature, 1.0)  # 最高1.0

        response = await self._client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=temperature,
            max_tokens=100,
        )

        rewritten = response.choices[0].message.content
        if not rewritten:
            return query

        return rewritten.strip()

    def _get_rewrite_strategy(self, attempt: int = 0) -> str:
        """
        返回统一的改写策略 prompt。

        专门针对猫鼠卡通素材库优化。
        """
        return """Convert song lyrics to cartoon video search queries.

RULES:
1. Use ONLY "cat" or "mouse" as characters (NEVER use names)
2. Format: [character] + [action/emotion], 3-6 words
3. Focus on emotions, not literal meanings

EXAMPLES:
"I'm preying on you" → cat stalking mouse
"Hunt you down" → cat chasing aggressively
"Counting stars" → cat looking up dreamy
"Losing sleep" → cat restless worried
"Heart on fire" → cat passionate excited
"Yeah yeah yeah" → cat jumping happy
"啦啦啦" → mouse dancing joyful
"Roar!" → cat roaring fierce
"写一封信" → cat writing letter
"想念你" → cat looking sad lonely

WRONG (never do this):
❌ Objects without characters: "perfume bottle", "stage"
❌ Repeating input: "yeah yeah" → "yeah yeah"
❌ Too literal: "counting stars" → "counting coins"

Lyrics:"""

"""查询改写模块：将抽象歌词转换为具体视觉描述。"""

from __future__ import annotations

import structlog
from openai import AsyncOpenAI

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)


class QueryRewriter:
    """使用 LLM 将抽象/隐喻的歌词改写为具体的视觉场景描述。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._enabled = settings.query_rewrite_enabled
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url
        self._client: AsyncOpenAI | None = None
        self._cache: dict[str, str] = {}

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

        # 为不同的尝试次数构建缓存键
        cache_key = f"{original_query}::{attempt}"

        # 检查缓存
        if cache_key in self._cache:
            logger.debug(
                "query_rewriter.cache_hit",
                original=original_query,
                attempt=attempt,
                rewritten=self._cache[cache_key],
            )
            return self._cache[cache_key]

        try:
            rewritten = await self._call_llm(original_query, attempt)
            self._cache[cache_key] = rewritten
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
            return original_query

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

    def _get_rewrite_strategy(self, attempt: int) -> str:
        """
        根据尝试次数返回不同的改写策略。

        专门针对 Tom and Jerry 卡通素材库优化。

        - 策略 0：卡通场景转换（主要策略）
        - 策略 1：动作强化（备用策略）
        - 策略 2：通用卡通关键词（兜底策略）
        """

        # 策略 0: 卡通场景转换 (Cartoon Scene Conversion)
        # 核心：将抽象歌词转换为具体的卡通动画场景描述
        strategy_0 = """You are a video search query optimizer for a Tom and Jerry cartoon library.

Your task: Convert song lyrics into **concrete visual scene descriptions** that would match Tom and Jerry cartoon clips.

**IMPORTANT RULES:**
1. Output MUST describe **visible actions or scenes** in a cartoon
2. Focus on: chasing, running, hiding, fighting, sneaking, eating, sleeping, surprised reactions
3. Include character descriptions when relevant: "cat chasing mouse", "mouse running away"
4. Keep output SHORT: 3-8 English words only
5. NO abstract concepts - only things you can SEE in a cartoon
6. NO emotional words unless they show on face (angry face, scared expression)

**Examples:**
"Baby I'm preying on you tonight" → "cat stalking mouse at night"
"Hunt you down eat you alive" → "cat chasing and catching mouse"
"Just like animals" → "wild cat and mouse fighting"
"Maybe you think that you can hide" → "mouse hiding in hole, cat searching"
"I can smell your scent from miles" → "cat sniffing and tracking mouse"
"You can find other fish in the sea" → "fish swimming in water, ocean scene"
"I can still hear you making that sound" → "cat with big ears listening"
"The beast inside" → "angry cat with fierce expression"
"Don't tell no lie" → "cat and mouse arguing, pointing finger"
"Yeah yeah yeah" → "characters dancing or celebrating"
"I love your lies" → "cat and mouse tricking each other"
"You're like a drug" → "cat dizzy or hypnotized"
"Run free" → "mouse running fast escaping"

Lyrics to convert:"""

        # 策略 1: 动作强化模式 (Action Boost Mode)
        # 核心：当第一次搜索失败时，使用更通用的卡通动作
        strategy_1 = """You are a cartoon video search assistant. Previous search failed.

Now convert the lyrics to **high-action cartoon scenes** that are common in Tom and Jerry.

**Rules:**
1. Use GENERIC cartoon actions: chase scene, fight scene, explosion, running, falling, crashing
2. Keep it simple: 2-5 words
3. Focus on MOVEMENT and ACTION

**Examples:**
"I can't stop" → "character running fast"
"Breaking apart" → "things breaking and crashing"
"Feel the heat" → "fire and explosion scene"
"Lost in your eyes" → "character staring with big eyes"
Any emotional lyrics → "cartoon character reaction shot"

Lyrics:"""

        # 策略 2: 通用卡通关键词 (Generic Cartoon Keywords)
        # 核心：兜底策略，确保至少能搜到卡通画面
        strategy_2 = """Extract 1-2 simple cartoon-related keywords. Search is very difficult.

**Rules:**
1. Output only 1-2 simple English words
2. Must be something visible in cartoons
3. Prefer: cat, mouse, chase, run, house, kitchen, garden, fight

**Examples:**
Any hunting/chasing lyrics → "cat mouse chase"
Any hiding lyrics → "mouse hiding"
Any emotional lyrics → "cartoon reaction"
Any love lyrics → "characters together"
Anything else → "Tom Jerry scene"

Lyrics:"""

        strategies = {0: strategy_0, 1: strategy_1, 2: strategy_2}

        return strategies.get(attempt, strategy_2)

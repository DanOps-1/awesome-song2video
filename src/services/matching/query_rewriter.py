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
        核心原则：输出必须包含角色（Tom/Jerry/cat/mouse），禁止纯物品/场景描述。

        - 策略 0：角色动作优先（主要策略）
        - 策略 1：角色表情特写（备用策略）
        - 策略 2：角色互动兜底（兜底策略）
        """

        # 策略 0: 角色动作优先 (Character Action First)
        # 核心：必须输出角色+动作，禁止纯物品/场景
        strategy_0 = """You are a video search query optimizer for a Tom and Jerry cartoon library.

Your task: Convert song lyrics into **character action descriptions** for Tom and Jerry clips.

**CRITICAL RULES - MUST FOLLOW:**
1. Output MUST contain a CHARACTER: "Tom", "Jerry", "cat", "mouse", or "characters"
2. Output MUST contain an ACTION or EXPRESSION the character is doing
3. NEVER output objects only (NO: "perfume bottle", "stage", "gifts", "electricity")
4. NEVER output scenes without characters (NO: "kitchen scene", "garden view")
5. Keep output SHORT: 3-8 English words
6. Focus on CHARACTER CLOSE-UPS with clear facial expressions or body movements

**GOOD Examples (character + action):**
"Baby I'm preying on you tonight" → "Tom stalking Jerry at night"
"Hunt you down eat you alive" → "Tom chasing Jerry aggressively"
"Just like animals" → "Tom and Jerry fighting wildly"
"I can smell your scent from miles" → "Tom sniffing with big nose"
"The beast inside" → "Tom angry face close-up growling"
"You can't deny" → "Tom screaming with open mouth"
"Yeah yeah yeah" → "Tom and Jerry dancing together"
"I love your lies" → "Jerry tricking Tom smiling"
"Feel the heat" → "Tom sweating nervous expression"
"Run free" → "Jerry running fast escaping"

**BAD Examples (DO NOT OUTPUT LIKE THIS):**
"I can smell your scent" → ❌ "perfume bottles on table" (no character!)
"The beast inside" → ❌ "dark stage scene" (no character!)
"Feel the heat" → ❌ "fire and flames" (no character!)

Lyrics to convert:"""

        # 策略 1: 角色表情特写 (Character Expression Close-up)
        # 核心：当第一次搜索分数低时，聚焦角色面部表情
        strategy_1 = """You are a cartoon video search assistant. Focus on CHARACTER EXPRESSIONS.

Convert lyrics to **Tom or Jerry facial expression/reaction shots**.

**STRICT RULES:**
1. Output MUST start with "Tom" or "Jerry" or "cat" or "mouse"
2. Focus on FACE and EXPRESSION: shocked, angry, happy, scared, crying, laughing
3. Keep it simple: 3-5 words
4. Prefer close-up shots of character faces

**Examples:**
"I can't stop" → "Tom running panicked face"
"Breaking apart" → "Jerry crying sad expression"
"Feel the heat" → "Tom sweating scared face"
"Lost in your eyes" → "Tom love-struck dreamy eyes"
"The beast inside" → "Tom fierce angry growling"
"You can't deny" → "Tom shocked surprised face"
Any emotional lyrics → "Tom exaggerated reaction face"

Lyrics:"""

        # 策略 2: 角色互动兜底 (Character Interaction Fallback)
        # 核心：兜底策略，确保至少有角色互动画面
        strategy_2 = """Output a simple Tom and Jerry character interaction. This is the final fallback.

**ABSOLUTE RULES:**
1. Output MUST contain "Tom" or "Jerry"
2. Maximum 4 words
3. Simple common actions only

**Examples:**
Any hunting/chasing lyrics → "Tom chasing Jerry"
Any hiding lyrics → "Jerry hiding from Tom"
Any emotional lyrics → "Tom surprised face"
Any love lyrics → "Tom and Jerry together"
Any angry lyrics → "Tom angry at Jerry"
Any happy lyrics → "Jerry happy dancing"
Anything else → "Tom Jerry interaction"

Lyrics:"""

        strategies = {0: strategy_0, 1: strategy_1, 2: strategy_2}

        return strategies.get(attempt, strategy_2)

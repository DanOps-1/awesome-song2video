"""查询改写模块：将抽象歌词转换为具体视觉描述。"""

from __future__ import annotations

import re
import structlog
from openai import AsyncOpenAI

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)

# 角色名称关键词（用于验证查询是否包含 Tom & Jerry 角色）
CHARACTER_KEYWORDS = [
    "tom", "jerry", "cat", "mouse", "kitten", "kitty",
    "feline", "rodent", "tabby", "猫", "鼠", "老鼠",
]


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

    def _contains_character(self, query: str) -> bool:
        """检查查询是否包含 Tom & Jerry 角色关键词"""
        query_lower = query.lower()
        for keyword in CHARACTER_KEYWORDS:
            if keyword in query_lower:
                return True
        return False

    def _ensure_character_in_query(self, query: str) -> str:
        """
        确保查询包含角色名称。

        如果查询不包含任何角色关键词，在前面添加 "Tom and Jerry"。
        这样可以确保 TwelveLabs 搜索结果更可能包含主角。
        """
        if self._contains_character(query):
            return query

        # 不包含角色名称，添加 "Tom and Jerry" 前缀
        fixed_query = f"Tom and Jerry {query}"
        logger.info(
            "query_rewriter.character_added",
            original=query,
            fixed=fixed_query,
            message="查询缺少角色名称，已添加 'Tom and Jerry' 前缀",
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

            # 🎬 强制角色验证：确保查询包含 Tom/Jerry 角色
            rewritten = self._ensure_character_in_query(rewritten)

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

        专门针对 Tom and Jerry 卡通素材库优化。
        核心原则：输出必须包含角色（Tom/Jerry/cat/mouse），禁止纯物品/场景描述。
        """

        # 统一策略：角色优先 + 动作/表情 + 简洁输出 + 拟声词智能处理
        return """You are a video search query optimizer for a Tom and Jerry cartoon library.

Your task: Convert song lyrics into **character action descriptions** for Tom and Jerry clips.

**CRITICAL RULES - MUST FOLLOW:**
1. Output MUST contain a CHARACTER: "Tom", "Jerry", "cat", or "mouse"
2. Output MUST contain an ACTION or EXPRESSION
3. NEVER output objects only (NO: "perfume bottle", "stage", "gifts", "electricity")
4. NEVER output scenes without characters (NO: "kitchen scene", "garden view")
5. Keep output SHORT: 3-6 English words only
6. Prefer character close-ups with facial expressions or clear body movements
7. Understand the EMOTIONAL/METAPHORICAL meaning, NOT literal meaning

**METAPHORICAL LYRICS - Understand the emotion, not literal words:**
- "counting stars" = romantic/dreamy/hopeful → "Tom Jerry looking up dreamy" (NOT counting objects!)
- "losing sleep" = worried/anxious → "Tom tossing turning worried" (NOT just sleeping)
- "praying hard" = hoping/wishing → "Tom hands together wishing" (NOT religious scene)
- "sold" = betrayed/lost hope → "Tom sad disappointed"
- "doing the right thing" = moral struggle → "Tom conflicted thinking"
- "fire inside" = passion/anger → "Tom fierce determined" (NOT literal fire)
- "heart on fire" = love/passion → "Tom love-struck dreamy" (NOT burning)

**SPECIAL RULE FOR INTERJECTIONS/ONOMATOPOEIA:**
Some lyrics contain interjections or sound effects. Handle them intelligently:

1. **Meaningful sound effects** (keep the meaning!):
   - "oww/howl/awoo" (wolf howl) → "Tom howling like wolf"
   - "roar/grr" (growl) → "Tom growling fierce"
   - "meow/purr" → "Tom meowing"
   - "boom/bang/crash" → "Tom crashing explosion"
   - "splash" → "Tom falling into water"

2. **Pure filler interjections** (convert to high-energy action):
   - "yeah/oh/ah/hey" alone → "Tom jumping excited"
   - "la la la/na na na" alone → "Jerry dancing happy"

3. **Mixed lyrics with interjections** (focus on the semantic content):
   - "Just like animals oww" → "Tom howling like wild animal" (oww = wolf howl, keep it!)
   - "Hunt you down yeah yeah" → "Terry aggressively" (yeah = filler, ignore)

**GOOD Examples:**
"Baby I'm preying on you tonight" → "Tom stalking Jerry"
"Hunt you down eat you alive" → "Tom chasing Jerry aggressively"
"Just like animals oww" → "Tom howling like wild animal"
"animals-mals yeah oww" → "Tom howling fiercely"
"Yeah yeah yeah" (alone) → "Tom jumping excited"
"Oh oh oh~" (alone) → "Jerry running fast"
"啊啊啊" (alone) → "Tom screaming shocked"
"啦啦啦" (alone) → "Jerry dancing happy"
"Whoa~" → "Tom surprised face"
"嘿嘿嘿" → "Tom sneaking mischievous"
"Roar!" → "Tom roaring fierce"
"Meow~" → "Tom meowing cute"
"Counting stars" → "Tom Jerry looking up night sky dreamy"
"Losing sleep" → "Tom restless worried"
"Praying hard" → "Tom wishing hoping"
"Dreaming about" → "Tom daydreaming happy"

**BAD Examples (NEVER output like this):**
"I can smell your scent" → ❌ "perfume bottles on table"
"The beast inside" → ❌ "dark stage scene"
"Yeah yeah" → ❌ "yeah yeah" (never repeat the original)
"啊啊啊" → ❌ "啊啊啊" (never repeat the original)
"Counting stars" → ❌ "counting money coins" (literal interpretation!)
"Losing sleep" → ❌ "sleeping bed" (too literal!)
"Keep out" → ❌ "keep out sign fence" (object, no character!)

Lyrics to convert:"""

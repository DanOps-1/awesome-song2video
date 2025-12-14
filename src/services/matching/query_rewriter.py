"""查询改写模块：将抽象歌词转换为具体视觉描述。"""

from __future__ import annotations

import random
import re
import structlog
from openai import AsyncOpenAI

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)

# 拟声词/感叹词模式 - 这些词没有语义，应该匹配高能量动作画面
INTERJECTION_PATTERNS = [
    r"^(oh+|ah+|eh+|uh+|yeah+|ye+ah|ya+h|wo+|wow+|oo+h|aa+h|hey+|ha+|hah+|whoa+|yea+)\s*[~!]*$",
    r"^(la+|na+|da+|ba+|sha+|do+|re+|mi+|fa+|so+)\s*(la+|na+|da+|ba+|sha+|do+|re+|mi+|fa+|so+)*\s*[~!]*$",
    r"^[~!?。，、\s]*$",  # 纯标点/空白
]

# 高能量动作查询词 - 用于拟声词/感叹词
HIGH_ENERGY_QUERIES = [
    "Tom Jerry dramatic action",
    "Tom jumping excited",
    "Jerry running fast",
    "Tom and Jerry chase explosion",
    "Tom screaming shocked",
    "Jerry celebrating victory",
    "Tom crashing falling",
    "dramatic cartoon moment",
    "Tom angry attack",
    "Jerry escape dramatic",
    "Tom surprised face",
    "cartoon action climax",
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
        # 编译拟声词正则表达式
        self._interjection_patterns = [re.compile(p, re.IGNORECASE) for p in INTERJECTION_PATTERNS]
        # 高能量查询索引，用于轮换
        self._high_energy_index = 0

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

    def _is_interjection(self, text: str) -> bool:
        """
        检测文本是否为拟声词/感叹词。

        这类词没有实际语义，如：
        - yeah, oh, ah, wow, hey
        - la la la, na na na
        - 纯标点符号
        """
        cleaned = text.strip().lower()
        if not cleaned:
            return True

        for pattern in self._interjection_patterns:
            if pattern.match(cleaned):
                return True
        return False

    def _get_high_energy_query(self) -> str:
        """获取一个高能量动作查询词（轮换使用）。"""
        query = HIGH_ENERGY_QUERIES[self._high_energy_index % len(HIGH_ENERGY_QUERIES)]
        self._high_energy_index += 1
        return query

    async def rewrite(self, original_query: str, attempt: int = 0) -> str:
        """
        改写查询文本。

        Args:
            original_query: 原始歌词文本
            attempt: 重试次数（0=第一次改写，1=第二次改写...）

        Returns:
            改写后的查询，如果未启用或失败则返回原始文本
        """
        # 🎵 特殊处理：拟声词/感叹词 → 高能量动作画面
        # 这类词（yeah, oh, ah, la la la 等）没有语义，不应该用 LLM 改写
        # 而应该直接匹配高能量/卡点画面
        if self._is_interjection(original_query):
            high_energy_query = self._get_high_energy_query()
            logger.info(
                "query_rewriter.interjection_detected",
                original=original_query,
                rewritten=high_energy_query,
                message="拟声词/感叹词 → 高能量动作画面",
            )
            return high_energy_query

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

    def _get_rewrite_strategy(self, attempt: int = 0) -> str:
        """
        返回统一的改写策略 prompt。

        专门针对 Tom and Jerry 卡通素材库优化。
        核心原则：输出必须包含角色（Tom/Jerry/cat/mouse），禁止纯物品/场景描述。
        """

        # 统一策略：角色优先 + 动作/表情 + 简洁输出
        return """You are a video search query optimizer for a Tom and Jerry cartoon library.

Your task: Convert song lyrics into **character action descriptions** for Tom and Jerry clips.

**CRITICAL RULES - MUST FOLLOW:**
1. Output MUST contain a CHARACTER: "Tom", "Jerry", "cat", or "mouse"
2. Output MUST contain an ACTION or EXPRESSION
3. NEVER output objects only (NO: "perfume bottle", "stage", "gifts", "electricity")
4. NEVER output scenes without characters (NO: "kitchen scene", "garden view")
5. Keep output SHORT: 3-6 English words only
6. Prefer character close-ups with facial expressions or clear body movements

**GOOD Examples (character + action/expression):**
"Baby I'm preying on you tonight" → "Tom stalking Jerry"
"Hunt you down eat you alive" → "Tom chasing Jerry aggressively"
"Just like animals" → "Tom and Jerry fighting"
"I can smell your scent from miles" → "Tom sniffing tracking"
"The beast inside" → "Tom angry fierce face"
"You can't deny" → "Tom screaming open mouth"
"Yeah yeah yeah" → "Tom Jerry dancing"
"I love your lies" → "Jerry tricking Tom"
"Feel the heat" → "Tom sweating scared"
"Run free" → "Jerry running escaping"
"Breaking apart" → "Jerry crying sad"
"Lost in your eyes" → "Tom love-struck dreamy"
"I can't stop" → "Tom running panicked"

**BAD Examples (NEVER output like this):**
"I can smell your scent" → ❌ "perfume bottles on table"
"The beast inside" → ❌ "dark stage scene"
"Feel the heat" → ❌ "fire and flames"

Lyrics to convert:"""

"""查询改写模块 - 将抽象歌词转换为具体视觉描述

使用 LLM 进行三层递进式改写：
- 策略 0: 语义简化（保留核心语义）
- 策略 1: 动态氛围（高视觉冲击力）
- 策略 2: 极简名词（物体关键词）
"""

from __future__ import annotations

import structlog
from openai import AsyncOpenAI

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)


class QueryRewriter:
    """使用 LLM 将抽象/隐喻的歌词改写为具体的视觉场景描述"""

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
        """改写查询文本

        Args:
            original_query: 原始歌词文本
            attempt: 重试次数（0=第一次改写，1=第二次...）

        Returns:
            改写后的查询，如果未启用或失败则返回原始文本
        """
        if not self._enabled or not self._client:
            return original_query

        cache_key = f"{original_query}::{attempt}"

        if cache_key in self._cache:
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
        """调用 LLM API 进行改写"""
        if not self._client:
            return query

        system_prompt = self._get_rewrite_strategy(attempt)

        # 根据尝试次数调整温度，增加多样性
        temperature = 0.3 + (attempt * 0.2)
        temperature = min(temperature, 1.0)

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
        """根据尝试次数返回不同的改写策略"""

        # 策略 0: 语义简化模式
        strategy_0 = """你是一位歌词语义提取专家。
请将输入的歌词转换为**简洁但保留核心语义**的英文描述，用于视频素材搜索。

**原则：**
1. **保留核心动作和物体：** 提取主要的动作、人物、物体。
2. **保留关键情感词：** 如果有明显的情感，保留它们。
3. **保留生动意象：** 如果有独特的比喻或画面，保留它们。
4. **去除冗余修饰：** 去除过于抽象的修饰词。
5. **翻译成英文：** 最终输出简洁的英文短语（5-15个词）。

当前歌词："""

        # 策略 1: 动态氛围模式
        strategy_1 = """你是一个视频素材助理。
上一轮搜索失败了。
现在，请将歌词转化为具有**强烈视觉冲击力**的英文描述。

**规则：**
1. 如果没有具体物体，描述一个符合歌曲情绪的**通用高动态场景**。
2. 重点关注**动态（Movement）**：Mashup 需要画面是动的，不要静态图。
3. 保持描述简短有力。

当前歌词："""

        # 策略 2: 极简物体兜底
        strategy_2 = """你是一个关键词提取器。
搜索非常困难。请直接提取歌词中任何**可见的物理物体**，翻译成英文。

**规则：**
1. 只输出 1-2 个英文名词。
2. 不要动作，不要形容词，只要物体。

当前歌词："""

        strategies = {
            0: strategy_0,
            1: strategy_1,
            2: strategy_2,
        }

        return strategies.get(attempt, strategy_2)

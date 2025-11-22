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

        - 策略 0：极致缩句（Abbreviation）。提取主谓宾，去除修饰。
        - 策略 1：动作与视觉冲击（High Impact Action）。如果字面无法搜到，搜动作。
        - 策略 2：极简名词（Keywords）。
        """

        # 策略 0: 极致缩句模式 (Sentence Abbreviation Mode)
        # 核心：直接缩句，去除修饰，只保留核心动作和物体。
        strategy_0 = """你是一位歌词缩句专家。
请将输入的歌词进行**极致缩句**，只保留核心的**主语+谓语+宾语**（SVO结构），去除所有形容词、副词、状语等修饰成分。
最后将缩句后的结果**翻译成英文**。

**原则：**
1. **只留主干：** 谁（Subject）+ 做了什么（Verb）+ 什么（Object）。
2. **去除修饰：** 不要形容词（如"火红的"）、不要副词（如"愉快地"）、不要地点（如"在山上"）。
3. **简单直接：** 不要进行联想或画面扩展，完全忠实于原句的主干。

**示例：**
输入："它在火红的山上愉快的唱着歌"
输出："It is singing"

输入："我看见一只白色的鸟飞过天空"
输出："I see a bird"

输入："破碎的镜子映出我的脸"
输出："Mirror reflects face"

输入："在那遥远的地方有位好姑娘"
输出："There is a girl"

当前歌词："""

        # 策略 1: 动态氛围模式 (Dynamic Vibe Mode)
        # 核心：当歌词完全抽象（没有物体）时，使用高动态的通用画面。
        strategy_1 = """你是一个视频素材助理。
上一轮搜索失败了。
现在，请将歌词转化为具有**强烈视觉冲击力**或**特定氛围**的英文描述。

**规则：**
1. 如果没有具体物体，描述一个符合歌曲情绪的**通用高动态场景**（如：奔跑、下雨、城市车流、爆炸）。
2. 重点关注**动态（Movement）**：Mashup 需要画面是动的，不要静态图。
3. 保持描述简短有力。

**示例：**
输入："I can't take it anymore" (情绪崩溃)
输出："Person screaming underwater, bubbles rising, chaotic movement."

输入："Love is in the air" (抽象)
输出："Pink clouds moving fast in the sky, time lapse, dreamy atmosphere."

当前歌词："""

        # 策略 2: 极简物体兜底 (Object Keywords)
        # 核心：只要画面里有这个东西就行。
        strategy_2 = """你是一个关键词提取器。
搜索非常困难。请直接提取歌词中任何**可见的物理物体**，翻译成英文。

**规则：**
1. 只输出 1-2 个英文名词。
2. 不要动作，不要形容词，只要物体。

**示例：**
输入："手里的玫瑰已枯萎"
输出："dead rose"

输入："透过窗户看世界"
输出："window, glass"

当前歌词："""

        strategies = {
            0: strategy_0,
            1: strategy_1,
            2: strategy_2
        }

        return strategies.get(attempt, strategy_2)

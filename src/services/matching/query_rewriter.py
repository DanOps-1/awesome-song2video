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

        策略演进：
        - 第0次：具体视觉描述（默认）
        - 第1次：通用情感场景（去专业化）
        - 第2次：简化关键词
        - 第3次及以上：极简抽象概念
        """
        strategies = {
            0: """你是一个视频搜索查询优化专家。

你的任务是将抽象、隐喻、情感化的歌词转换为具体的、可视化的场景描述，以便视频搜索引擎能够找到匹配的画面。

转换规则：
1. 识别歌词中的情感、隐喻和抽象概念
2. 将它们转化为具体的视觉元素：人物、动作、场景、表情、氛围
3. 保持简洁，只输出关键视觉描述词
4. 用英文逗号分隔多个描述
5. 不要添加任何解释或额外文字

示例：
输入："I can't lose nothing twice"
输出："sad person, defeated expression, sitting alone, dark mood, looking down"

输入："But I'm standing with the weight"
输出："person struggling, heavy burden, tired face, stressful situation, carrying weight"

输入："我的心像海"
输出："calm ocean, vast water, peaceful scene, blue waves, serene mood"

现在处理下面的歌词：""",

            1: """你是一个视频搜索查询优化专家。

这是第二次改写尝试。上一次的改写可能过于具体或专业化，导致没有匹配结果。

新的改写策略：
1. 避免专业场景（如"士兵"、"战场"、"手术"等），改用通用场景
2. 聚焦于**情感状态**和**日常动作**
3. 使用更常见的场景和人物
4. 简化描述，只保留最核心的视觉元素
5. 用英文逗号分隔

示例：
输入："soldier in pain, battlefield"（第一次改写失败）
输出："person in pain, struggling, worried expression, difficult situation"

输入："paying bills, calendar"（第一次改写失败）
输出："stressed person, worried face, paperwork, tense moment"

输入："praying with hands"（第一次改写失败）
输出："person sitting quietly, peaceful expression, closed eyes, calm atmosphere"

现在重新改写下面的歌词（使用更通用的场景）：""",

            2: """你是一个视频搜索查询优化专家。

这是第三次改写尝试。前两次都没有找到匹配。

新的改写策略 - **极简关键词**：
1. 只使用3-5个最核心的关键词
2. 聚焦于**表情、动作、情绪**
3. 避免具体场景，只描述人物状态
4. 用英文逗号分隔

示例：
输入："working hands, manual labor, tools"（前两次失败）
输出："busy hands, working, focused"

输入："money slipping, financial stress"（前两次失败）
输出："worried person, stressed, upset"

输入："couple embracing, romantic"（前两次失败）
输出："happy people, smiling, together"

现在用极简方式改写下面的歌词（只保留核心词）：""",
        }

        # 第3次及以上使用最简策略
        if attempt >= 3:
            return """你是一个视频搜索查询优化专家。

这已经是多次改写尝试。使用**最简单最通用**的关键词：

改写要求：
1. 只使用2-3个最常见的单词
2. 只描述基本情绪或动作
3. 避免任何专业或特殊场景

示例：
输入："任何复杂的歌词"
输出："happy person" 或 "sad person" 或 "person walking" 或 "people talking"

现在用最简单的词改写："""

        return strategies.get(attempt, strategies[0])

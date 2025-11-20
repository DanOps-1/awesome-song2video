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

        针对快节奏混剪（Mashup）优化：
        - 策略 0：极致的字面意思（Literal B-Roll）。歌词说什么物体，就给什么物体。
        - 策略 1：动作与视觉冲击（High Impact Action）。如果字面无法搜到，搜动作。
        - 策略 2：极简名词（Keywords）。
        """

        # 策略 0: 字面素材模式 (Literal B-Roll Mode)
        # 核心：拒绝隐喻。歌词提到"火"就搜"火"，提到"跑"就搜"跑"。
        strategy_0 = """你是一位专门制作**快节奏混剪视频（Mashup）**的素材搜索专家。
你的任务是根据歌词，生成最直接、最字面的英文画面描述（B-Roll Footage）。

**核心原则：字面对应（Literal Matching）**
混剪视频节奏很快，画面必须与歌词中的**名词**或**动词**直接对应，观众才能瞬间看懂。

**严格规则：**
1. **拒绝隐喻：** 如果歌词是"我的心在燃烧"，不要搜"伤心的人"，要搜"Fire burning"（火焰）。如果歌词是"时间流逝"，要搜"Clock ticking"（时钟）。
2. **提取视觉实体：** 找出歌词中最具象的物体（名词）或动作（动词）。
3. **画面填满：** 描述要具体，强调特写（Close-up）或具有视觉冲击力的画面。
4. **输出格式：** 一个简短、有力的英文句子。

**示例：**
输入："熊熊火焰燃烧" (Raging fire)
输出："A large fire burning intensely, flames filling the screen, close-up."

输入："打碎这枷锁" (Break the chains)
输出："Metal chains breaking, iron links shattering, slow motion."

输入："开着车去远方" (Driving far away)
输出："A car driving fast on a highway, motion blur, POV shot."

输入："时间不够了" (Time is running out)
输出："A clock ticking fast, time lapse, hourglass sand falling."

输入："我的心像石头" (Heart like a stone)
输出："A large grey stone on the ground, static shot, realistic texture." (注意：这里要真的石头，不要隐喻)

当前歌词："""

        # 策略 1: 动态氛围模式 (Dynamic Vibe Mode)
        # 核心：当歌词完全抽象（没有物体）时，使用高动态的通用画面。
        strategy_1 = """你是一个视频素材助理。
上一轮的"字面搜索"失败了（可能歌词太抽象，没有具体物体）。
现在，请将歌词转化为具有**强烈视觉冲击力**或**特定氛围**的英文描述。

**规则：**
1. 如果没有具体物体，描述一个符合歌曲情绪的**通用高动态场景**（如：奔跑、下雨、城市车流、爆炸）。
2. 重点关注**动态（Movement）**：Mashup 需要画面是动的，不要静态图。
3. 保持描述简短有力。

**示例：**
输入："I can't take it anymore" (情绪崩溃)
输出："Person screaming underwater, bubbles rising, chaotic movement." (具象化情绪)

输入："Love is in the air" (抽象)
输出："Pink clouds moving fast in the sky, time lapse, dreamy atmosphere." (氛围化)

输入："Everything is changing" (抽象)
输出："City traffic time lapse at night, fast lights, busy street." (通用动态)

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

输入："像子弹一样穿过"
输出："flying bullet"

输入："透过窗户看世界"
输出："window, glass"

当前歌词："""

        strategies = {
            0: strategy_0,
            1: strategy_1,
            2: strategy_2
        }

        return strategies.get(attempt, strategy_2)

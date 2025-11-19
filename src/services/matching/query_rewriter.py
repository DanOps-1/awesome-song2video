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
            
            注意：指令是中文的，但要求模型输出英文搜索词（以获得更好的向量匹配效果）。
            如果你使用的是纯中文向量模型（如 Taiyi 或 AltCLIP），请将提示词中的"英文"改为"中文"。
            """

            # 策略 0: 电影导演模式 (Cinematic Mode)
            # 核心：意象具象化。把"悲伤"变成"下雨的窗户"，增加光影和镜头感。
            strategy_0 = """你是一位专业的 AI 音乐视频（MV）导演。
    你的任务是将抽象的歌词转化为**详细的、电影感的英文画面描述**，以便视频搜索引擎能够找到匹配的素材。

    关键规则：
    1. **输出单个自然的英文句子**。不要输出逗号分隔的标签。
    2. **意象具象化（最重要）：** 如果歌词很抽象（例如"我的心冷得像冰"），请描述一个代表该意境的视觉场景（例如"A lonely figure standing in a snowy street under a blue street light"）。不要直译隐喻。
    3. **包含电影细节：** 必须提及光线（如 cinematic lighting, dark, sunny）、景别（如 close-up, wide shot）和动态（如 slow motion, running）。
    4. **不要解释：** 不要出现 "metaphor for..." 或 "symbolizes..." 之类的词，直接描述眼睛能看到的画面。

    示例：
    输入："I can't lose nothing twice"
    输出："A close-up shot of a man with a devastated expression sitting in a dark room, high contrast lighting, cinematic style."

    输入："But I'm standing with the weight"
    输出："A low-angle shot of a tired person walking slowly down a rainy street, carrying a heavy backpack, exhausted posture."

    输入："城市依然在沉睡"
    输出："A quiet city street at dawn, empty roads, soft blue morning light, static shot."

    当前歌词："""

            # 策略 1: 动作聚焦模式 (Action Mode)
            # 核心：当复杂描述搜不到时，简化为"谁+做什么"。
            strategy_1 = """你是一个视频检索助手。
    上一次的搜索过于复杂，没有找到结果。现在，请将歌词简化为**对物理动作或清晰情绪的简单英文描述**。

    规则：
    1. 只关注**主体（Who）**和**动作（What）**。
    2. 去掉光影、镜头角度、艺术风格等修饰词。
    3. 保持描述通用、宽泛。
    4. 输出简单的英文句子。

    示例：
    输入："I'm fighting a war inside my head"
    输出："A person holding their head in pain and looking stressed."

    输入："Running away from the truth"
    输出："A person running fast down a street."

    输入："阳光洒在我的脸上"
    输出："A happy person looking up at the sky smiling."

    当前歌词："""

            # 策略 2: 极简物体模式 (Object Mode)
            # 核心：兜底策略，只搜画面里肯定有的东西。
            strategy_2 = """你是一个关键词提取器。
    之前的搜索都失败了。我们需要找到任何相关的素材。
    请提取歌词中暗示的最具体的**物理物体**或**基本场景**，并翻译成英文。

    规则：
    1. 只输出 2-3 个具体的英文名词或短语。
    2. 不要包含情绪，不要包含动作，只要物体。
    3. 格式：英文单词或短语。

    示例：
    输入："Driving down the highway of life"
    输出："highway, car"

    输入："Time is ticking away"
    输出："clock on wall"

    输入："碎片散落一地"
    输出："broken glass, floor"

    当前歌词："""

            strategies = {
                0: strategy_0,
                1: strategy_1,
                2: strategy_2
            }

            # 超过2次尝试，默认使用策略2
            return strategies.get(attempt, strategy_2)

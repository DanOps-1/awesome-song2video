"""歌词翻译服务：将英文歌词翻译为中文。"""

from __future__ import annotations

import asyncio
import re

import structlog
from langdetect import detect, LangDetectException

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)

# 尝试导入可选依赖
try:
    from openai import AsyncOpenAI

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    AsyncOpenAI = None  # type: ignore[misc,assignment]

try:
    import translators as ts

    HAS_TRANSLATORS = True
except ImportError:
    HAS_TRANSLATORS = False
    ts = None


def is_english(text: str) -> bool:
    """检测文本是否为英文。"""
    if not text or not text.strip():
        return False

    # 去除标点和数字
    clean_text = re.sub(r"[^\w\s]", "", text)
    clean_text = re.sub(r"\d+", "", clean_text)

    if not clean_text.strip():
        return False

    try:
        lang = detect(clean_text)
        return str(lang) == "en"
    except LangDetectException:
        # 回退：检查是否主要是ASCII字符
        ascii_ratio = sum(1 for c in clean_text if ord(c) < 128) / len(clean_text)
        return ascii_ratio > 0.8


class LyricsTranslator:
    """将英文歌词翻译为中文，支持多种翻译后端。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url
        self._client: AsyncOpenAI | None = None
        self._cache: dict[str, str] = {}
        self._use_free_api = False  # 是否使用免费API

        if HAS_OPENAI and self._api_key:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
            logger.info("lyrics_translator.initialized", backend="deepseek")
        elif HAS_TRANSLATORS:
            self._use_free_api = True
            logger.info("lyrics_translator.initialized", backend="free_api")
        else:
            logger.warning("lyrics_translator.disabled", reason="no_backend_available")

    async def translate_batch(self, lines: list[str]) -> list[str]:
        """
        批量翻译歌词行。

        Args:
            lines: 英文歌词列表

        Returns:
            中文翻译列表，与输入顺序对应
        """
        if not self._client and not self._use_free_api:
            return [""] * len(lines)

        # 检查缓存
        results: list[str | None] = []
        uncached_indices = []
        uncached_lines = []

        for i, line in enumerate(lines):
            if line in self._cache:
                results.append(self._cache[line])
            else:
                results.append(None)  # 占位
                uncached_indices.append(i)
                uncached_lines.append(line)

        if not uncached_lines:
            return [r or "" for r in results]

        # 批量翻译未缓存的行
        translations: list[str] = []
        try:
            if self._client:
                # 尝试使用 DeepSeek API
                translations = await self._translate_lines(uncached_lines)
            else:
                translations = []

            # 如果 DeepSeek 失败或未配置，使用免费 API
            if not translations or not any(translations):
                if self._use_free_api or HAS_TRANSLATORS:
                    logger.info("lyrics_translator.fallback_to_free_api")
                    translations = await self._translate_with_free_api(uncached_lines)

            for i, idx in enumerate(uncached_indices):
                translation = translations[i] if i < len(translations) else ""
                results[idx] = translation
                if translation:
                    self._cache[uncached_lines[i]] = translation

        except Exception as e:
            logger.error("lyrics_translator.batch_failed", error=str(e))
            # 尝试免费 API 作为最后手段
            if HAS_TRANSLATORS:
                try:
                    translations = await self._translate_with_free_api(uncached_lines)
                    for i, idx in enumerate(uncached_indices):
                        translation = translations[i] if i < len(translations) else ""
                        results[idx] = translation
                        if translation:
                            self._cache[uncached_lines[i]] = translation
                except Exception as e2:
                    logger.error("lyrics_translator.free_api_failed", error=str(e2))
                    for idx in uncached_indices:
                        results[idx] = ""
            else:
                for idx in uncached_indices:
                    results[idx] = ""

        return [r or "" for r in results]

    async def _translate_with_free_api(self, lines: list[str]) -> list[str]:
        """使用免费翻译 API 翻译。"""
        if not HAS_TRANSLATORS:
            return [""] * len(lines)

        translations = []
        for line in lines:
            try:
                # 使用 bing 翻译（稳定性较好）
                result = await asyncio.to_thread(
                    ts.translate_text,
                    line,
                    translator="bing",
                    from_language="en",
                    to_language="zh",
                )
                translations.append(result or "")
                logger.debug(
                    "lyrics_translator.free_api_success",
                    line=line[:30],
                    result=result[:30] if result else "",
                )
            except Exception as e:
                logger.warning(
                    "lyrics_translator.free_api_line_failed", line=line[:30], error=str(e)
                )
                translations.append("")

        return translations

    async def _translate_lines(self, lines: list[str]) -> list[str]:
        """调用 LLM 批量翻译。"""
        if not self._client or not lines:
            return [""] * len(lines)

        # 构建输入：每行一个歌词，用数字标记
        numbered_lines = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))

        system_prompt = """你是一位专业的歌词翻译专家。请将以下英文歌词翻译成中文。

要求：
1. 保持歌词的诗意和韵律感
2. 翻译要简洁流畅，适合作为字幕显示
3. 每行单独翻译，保持原有行数
4. 输出格式：每行一个翻译，用相同的数字标记

示例输入：
1. I love you more than words can say
2. You are the sunshine of my day

示例输出：
1. 爱你胜过千言万语
2. 你是我生命中的阳光"""

        try:
            response = await self._client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": numbered_lines},
                ],
                temperature=0.3,
                max_tokens=len(lines) * 50,  # 每行大约50个token
            )

            content = response.choices[0].message.content
            if not content:
                return [""] * len(lines)

            # 解析输出
            translations = self._parse_translations(content, len(lines))
            logger.info(
                "lyrics_translator.translated",
                input_count=len(lines),
                output_count=len(translations),
            )
            return translations

        except Exception as e:
            logger.error("lyrics_translator.api_failed", error=str(e))
            return [""] * len(lines)

    def _parse_translations(self, content: str, expected_count: int) -> list[str]:
        """解析 LLM 返回的翻译结果。"""
        translations = [""] * expected_count

        for line in content.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # 匹配 "1. 翻译内容" 格式
            match = re.match(r"^(\d+)\.\s*(.+)$", line)
            if match:
                idx = int(match.group(1)) - 1
                translation = match.group(2).strip()
                if 0 <= idx < expected_count:
                    translations[idx] = translation

        return translations


# 单例
_translator: LyricsTranslator | None = None


def get_translator() -> LyricsTranslator:
    """获取翻译器单例。"""
    global _translator
    if _translator is None:
        _translator = LyricsTranslator()
    return _translator

"""歌词转写与时间戳生成模块"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, TypedDict, cast

from anyio import to_thread
from pydub import AudioSegment
import whisper
import structlog

from src.audio.vocal_detector import detect_vocal_start
from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)

# 全局模型缓存
_WHISPER_MODEL = None


class WhisperSegment(TypedDict, total=False):
    """Whisper 转录结果片段"""

    text: str
    start: float
    end: float
    no_speech_prob: float
    avg_logprob: float


# 兼容旧代码的类型别名
WhisperResult = dict[str, str | float | int | None]


def _get_model() -> "whisper.Whisper":
    """获取或加载 Whisper 模型（单例）"""
    global _WHISPER_MODEL  # noqa: PLW0603
    if _WHISPER_MODEL is None:
        model_name = get_settings().whisper_model_name
        logger.info("transcriber.loading_model", model=model_name)
        _WHISPER_MODEL = whisper.load_model(model_name)
    return _WHISPER_MODEL


# 常见幻觉词表
HALLUCINATION_PHRASES = [
    "优优独播剧场",
    "YoYo Television",
    "独播剧场",
    "字幕",
    "Copyright",
    "All rights reserved",
    "Thank you for watching",
    "Thanks for watching",
    "Amara.org",
    "Subtitles by",
    "未经作者授权",
    "禁止转载",
]


def filter_segments(segments: list[dict]) -> list[dict]:
    """过滤 Whisper 幻觉和低质量片段。

    Args:
        segments: Whisper 返回的原始片段列表

    Returns:
        过滤后的片段列表
    """
    settings = get_settings()
    filtered = []

    for seg in segments:
        text = seg.get("text", "").strip()
        no_speech_prob = seg.get("no_speech_prob", 0.0)
        avg_logprob = seg.get("avg_logprob", 0.0)

        # 1. 检查非语音概率
        if no_speech_prob > settings.whisper_no_speech_threshold:
            continue

        # 2. 检查平均对数概率
        if avg_logprob < -1.0:
            continue

        # 3. 检查空文本
        if not text:
            continue

        # 4. 检查幻觉词
        is_hallucination = any(phrase.lower() in text.lower() for phrase in HALLUCINATION_PHRASES)
        if is_hallucination:
            continue

        filtered.append(seg)

    return filtered


async def transcribe_with_timestamps(
    audio_path: Path,
    language: str | None = None,
    prompt: str | None = None,
    skip_intro: bool = True,
    min_intro_duration: float = 5.0,
) -> Sequence[WhisperResult]:
    """使用 Whisper 模型进行语音转录，输出句级时间戳。

    Args:
        audio_path: 音频文件路径
        language: 语言代码（如 "zh", "en"），None 表示自动检测
        prompt: Whisper initial_prompt，用于引导转录风格
        skip_intro: 是否自动检测并跳过纯音乐前奏
        min_intro_duration: 最小前奏时长（秒），低于此值不跳过

    Returns:
        转录结果片段序列，每个片段包含 text, start, end 等字段

    Example:
        >>> segments = await transcribe_with_timestamps(
        ...     Path("song.mp3"),
        ...     language="zh",
        ...     skip_intro=True
        ... )
        >>> for seg in segments:
        ...     print(f"{seg['start']:.2f} - {seg['end']:.2f}: {seg['text']}")
    """
    audio = AudioSegment.from_file(audio_path)

    # 检测人声开始位置
    vocal_start_sec = 0.0
    if skip_intro:
        vocal_start_sec = detect_vocal_start(audio, window_sec=0.5, energy_percentile=60)

        # 如果检测到明显的前奏（>= min_intro_duration），则跳过
        if vocal_start_sec >= min_intro_duration:
            logger.info(
                "transcriber.skipping_intro",
                intro_duration_sec=vocal_start_sec,
                original_duration_sec=len(audio) / 1000,
            )
            audio = audio[int(vocal_start_sec * 1000) :]
        else:
            vocal_start_sec = 0.0

    # 导出为临时 WAV 文件
    temp = audio_path.with_suffix(".wav")
    if vocal_start_sec > 0:
        temp = audio_path.parent / f"{audio_path.stem}_skip{int(vocal_start_sec)}s.wav"

    audio.export(temp, format="wav")

    def _run_model() -> Sequence[WhisperResult]:
        model = _get_model()

        kwargs: dict[str, str | bool] = {"word_timestamps": True}
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["initial_prompt"] = prompt

        result = model.transcribe(temp.as_posix(), **kwargs)
        segments_any = result.get("segments", [])

        # 应用过滤逻辑
        clean_segments = filter_segments(segments_any)

        # 如果跳过了前奏，需要调整所有时间戳
        if vocal_start_sec > 0:
            for seg in clean_segments:
                if "start" in seg:
                    seg["start"] = seg["start"] + vocal_start_sec
                if "end" in seg:
                    seg["end"] = seg["end"] + vocal_start_sec

        return cast(Sequence[WhisperResult], clean_segments)

    segments = await to_thread.run_sync(_run_model)
    temp.unlink(missing_ok=True)
    return segments

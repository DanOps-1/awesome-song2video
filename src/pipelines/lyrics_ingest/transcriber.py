"""歌词转写与时间戳生成。"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, cast
import numpy as np

from anyio import to_thread
from pydub import AudioSegment  # type: ignore[import-untyped]
import whisper  # type: ignore[import-untyped]
import structlog

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)

WhisperResult = dict[str, str | float | int | None]
WHISPER_MODEL = None


def _get_model() -> "whisper.Whisper":
    global WHISPER_MODEL  # noqa: PLW0603 - 需要缓存模型实例
    if WHISPER_MODEL is None:
        model_name = get_settings().whisper_model_name
        WHISPER_MODEL = whisper.load_model(model_name)
    return WHISPER_MODEL


def _detect_vocal_start(audio: AudioSegment, window_sec: float = 0.5, energy_percentile: int = 60) -> float:
    """基于音频能量检测人声开始位置，用于跳过纯音乐前奏。

    Args:
        audio: 音频片段
        window_sec: 分析窗口（秒）
        energy_percentile: 能量阈值百分位数

    Returns:
        人声开始的时间（秒），如果检测失败返回 0.0
    """
    try:
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

        # 如果是立体声，转为单声道
        if audio.channels == 2:
            samples = samples.reshape((-1, 2)).mean(axis=1)

        # 计算每个窗口的 RMS 能量
        window_samples = int(window_sec * audio.frame_rate)
        num_windows = len(samples) // window_samples

        if num_windows < 2:
            return 0.0

        energies = []
        for i in range(num_windows):
            window = samples[i * window_samples:(i + 1) * window_samples]
            energy = np.sqrt(np.mean(window ** 2))  # RMS energy
            energies.append(energy)

        # 计算能量阈值
        energy_threshold = np.percentile(energies, energy_percentile)

        # 找到第一个超过阈值的窗口
        for i, energy in enumerate(energies):
            if energy > energy_threshold:
                vocal_start_sec = i * window_sec
                logger.info(
                    "transcriber.vocal_detection",
                    start_sec=vocal_start_sec,
                    energy=float(energy),
                    threshold=float(energy_threshold)
                )
                return vocal_start_sec

        return 0.0

    except Exception as e:
        logger.warning("transcriber.vocal_detection_failed", error=str(e))
        return 0.0


def _filter_segments(segments: list[dict]) -> list[dict]:
    """过滤 Whisper 幻觉和低质量片段。"""
    filtered = []
    
    # 常见幻觉词表
    hallucination_phrases = [
        "优优独播剧场", "YoYo Television", "独播剧场",
        "字幕", "Copyright", "All rights reserved", 
        "Thank you for watching", "Thanks for watching",
        "Amara.org", "Subtitles by",
        "未经作者授权", "禁止转载"
    ]
    
    for seg in segments:
        text = seg.get("text", "").strip()
        no_speech_prob = seg.get("no_speech_prob", 0.0)
        avg_logprob = seg.get("avg_logprob", 0.0)
        
        # 1. 检查非语音概率 (no_speech_prob)
        # 提高阈值以保留更多人声片段（特别是背景音乐较响的情况）
        if no_speech_prob > 0.9:
            continue
            
        # 2. 检查平均对数概率 (avg_logprob)
        if avg_logprob < -1.0:
            continue
            
        # 3. 检查空文本
        if not text:
            continue
            
        # 4. 检查幻觉词
        is_hallucination = False
        for phrase in hallucination_phrases:
            if phrase.lower() in text.lower():
                is_hallucination = True
                break
        if is_hallucination:
            continue
            
        filtered.append(seg)
        
    return filtered


async def transcribe_with_timestamps(
    audio_path: Path,
    language: str | None = None,
    prompt: str | None = None,
    skip_intro: bool = True,
) -> Sequence[WhisperResult]:
    """使用 Whisper large-v3 模型输出句级时间戳。

    Args:
        audio_path: 音频文件路径
        language: 语言代码（如 "zh", "en"）
        prompt: Whisper initial_prompt
        skip_intro: 是否自动检测并跳过纯音乐前奏（默认 True）
    """

    audio = AudioSegment.from_file(audio_path)

    # 检测人声开始位置
    vocal_start_sec = 0.0
    if skip_intro:
        vocal_start_sec = _detect_vocal_start(audio, window_sec=0.5, energy_percentile=60)

        # 如果检测到明显的前奏（>= 5秒），则跳过
        if vocal_start_sec >= 5.0:
            logger.info(
                "transcriber.skipping_intro",
                intro_duration_sec=vocal_start_sec,
                original_duration_sec=len(audio) / 1000
            )
            audio = audio[int(vocal_start_sec * 1000):]
        else:
            vocal_start_sec = 0.0

    temp = audio_path.with_suffix(".wav")
    if vocal_start_sec > 0:
        # 使用带后缀的临时文件名避免冲突
        temp = audio_path.parent / f"{audio_path.stem}_skip{int(vocal_start_sec)}s.wav"

    audio.export(temp, format="wav")

    def _run_model() -> Sequence[WhisperResult]:
        model = _get_model()
        # 构建参数
        kwargs = {"word_timestamps": False}
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["initial_prompt"] = prompt

        result = model.transcribe(temp.as_posix(), **kwargs)
        segments_any = result.get("segments", [])

        # 应用过滤逻辑
        clean_segments = _filter_segments(segments_any)

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

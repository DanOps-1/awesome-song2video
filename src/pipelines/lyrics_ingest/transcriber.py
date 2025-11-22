"""歌词转写与时间戳生成。"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, cast

from anyio import to_thread
from pydub import AudioSegment  # type: ignore[import-untyped]
import whisper  # type: ignore[import-untyped]

from src.infra.config.settings import get_settings


WhisperResult = dict[str, str | float | int | None]
WHISPER_MODEL = None


def _get_model() -> "whisper.Whisper":
    global WHISPER_MODEL  # noqa: PLW0603 - 需要缓存模型实例
    if WHISPER_MODEL is None:
        model_name = get_settings().whisper_model_name
        WHISPER_MODEL = whisper.load_model(model_name)
    return WHISPER_MODEL


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
        if no_speech_prob > 0.6:
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
) -> Sequence[WhisperResult]:
    """使用 Whisper large-v3 模型输出句级时间戳。"""

    audio = AudioSegment.from_file(audio_path)
    temp = audio_path.with_suffix(".wav")
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
        
        return cast(Sequence[WhisperResult], clean_segments)

    segments = await to_thread.run_sync(_run_model)
    temp.unlink(missing_ok=True)
    return segments

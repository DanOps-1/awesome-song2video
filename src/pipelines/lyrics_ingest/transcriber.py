"""歌词转写与时间戳生成。"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, cast

from anyio import to_thread
from pydub import AudioSegment  # type: ignore[import-untyped]
import whisper  # type: ignore[import-untyped]

from src.infra.config.settings import get_settings


WhisperResult = dict[str, str | float | int]
WHISPER_MODEL = None


def _get_model() -> "whisper.Whisper":
    global WHISPER_MODEL  # noqa: PLW0603 - 需要缓存模型实例
    if WHISPER_MODEL is None:
        model_name = get_settings().whisper_model_name
        WHISPER_MODEL = whisper.load_model(model_name)
    return WHISPER_MODEL


async def transcribe_with_timestamps(audio_path: Path) -> Sequence[WhisperResult]:
    """使用 Whisper large-v3 模型输出句级时间戳。"""

    audio = AudioSegment.from_file(audio_path)
    temp = audio_path.with_suffix(".wav")
    audio.export(temp, format="wav")

    def _run_model() -> Sequence[WhisperResult]:
        model = _get_model()
        result = model.transcribe(temp.as_posix(), word_timestamps=False)
        segments_any = result.get("segments", [])
        return cast(Sequence[WhisperResult], segments_any)

    segments = await to_thread.run_sync(_run_model)
    temp.unlink(missing_ok=True)
    return segments

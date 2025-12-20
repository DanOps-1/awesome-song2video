"""音频裁剪工具模块"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydub import AudioSegment
import structlog

logger = structlog.get_logger(__name__)


def cut_audio(
    audio_path: Path,
    start_ms: int,
    end_ms: int,
    output_path: Optional[Path] = None,
    format: str = "mp3",
) -> Path:
    """裁剪音频文件的指定时间段。

    Args:
        audio_path: 输入音频文件路径
        start_ms: 起始时间（毫秒）
        end_ms: 结束时间（毫秒）
        output_path: 输出文件路径，默认在同目录下生成
        format: 输出格式，默认 "mp3"

    Returns:
        裁剪后的音频文件路径

    Example:
        >>> output = cut_audio(Path("song.mp3"), 5000, 60000)
        >>> print(f"裁剪后的音频: {output}")
    """
    audio = AudioSegment.from_file(audio_path)
    clipped = audio[start_ms:end_ms]

    if output_path is None:
        output_path = audio_path.parent / f"{audio_path.stem}_cut.{format}"

    clipped.export(output_path, format=format)

    logger.info(
        "audio_cutter.cut",
        input=audio_path.name,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        output=output_path.name,
    )

    return output_path


def cut_audio_for_lyrics(
    audio_path: Path,
    first_lyric_start_ms: int,
    last_lyric_end_ms: int,
    output_path: Optional[Path] = None,
    format: str = "wav",
) -> Path:
    """根据歌词时间范围裁剪音频。

    专门用于视频混剪场景，将音频裁剪到只包含歌词的部分，
    以便与视频时间轴对齐。

    Args:
        audio_path: 原始音频文件路径
        first_lyric_start_ms: 第一句歌词开始时间（毫秒）
        last_lyric_end_ms: 最后一句歌词结束时间（毫秒）
        output_path: 输出文件路径
        format: 输出格式

    Returns:
        裁剪后的音频文件路径
    """
    duration_ms = last_lyric_end_ms - first_lyric_start_ms

    logger.info(
        "audio_cutter.cut_for_lyrics",
        audio=audio_path.name,
        lyric_start_ms=first_lyric_start_ms,
        lyric_end_ms=last_lyric_end_ms,
        duration_ms=duration_ms,
    )

    return cut_audio(
        audio_path,
        start_ms=first_lyric_start_ms,
        end_ms=last_lyric_end_ms,
        output_path=output_path,
        format=format,
    )


def get_audio_duration_ms(audio_path: Path) -> int:
    """获取音频文件时长（毫秒）。

    Args:
        audio_path: 音频文件路径

    Returns:
        时长（毫秒）
    """
    audio = AudioSegment.from_file(audio_path)
    return len(audio)


def normalize_audio(
    audio_path: Path,
    target_dBFS: float = -20.0,
    output_path: Optional[Path] = None,
) -> Path:
    """音频响度归一化。

    Args:
        audio_path: 输入音频文件路径
        target_dBFS: 目标响度（dBFS），默认 -20.0
        output_path: 输出文件路径

    Returns:
        归一化后的音频文件路径
    """
    audio = AudioSegment.from_file(audio_path)
    change_in_dBFS = target_dBFS - audio.dBFS
    normalized = audio.apply_gain(change_in_dBFS)

    if output_path is None:
        output_path = audio_path.parent / f"{audio_path.stem}_normalized{audio_path.suffix}"

    normalized.export(output_path, format=audio_path.suffix.lstrip("."))

    logger.info(
        "audio_cutter.normalize",
        input=audio_path.name,
        original_dBFS=round(audio.dBFS, 2),
        target_dBFS=target_dBFS,
        output=output_path.name,
    )

    return output_path

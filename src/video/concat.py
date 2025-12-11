"""视频拼接模块

使用 FFmpeg concat demuxer 实现无损视频拼接。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import structlog

from src.video.utils import run_ffmpeg

logger = structlog.get_logger(__name__)


def concat_videos(
    clips: Iterable[Path],
    output: Path,
    *,
    use_stream_copy: bool = True,
) -> Path:
    """拼接多个视频片段。

    使用 FFmpeg concat demuxer 实现拼接，支持流复制（无损）
    或重编码模式。

    Args:
        clips: 视频片段路径列表
        output: 输出文件路径
        use_stream_copy: 是否使用流复制（默认 True，更快）

    Returns:
        输出文件路径

    Raises:
        RuntimeError: 如果拼接失败

    Example:
        >>> clips = [Path("clip1.mp4"), Path("clip2.mp4")]
        >>> output = concat_videos(clips, Path("output.mp4"))
    """
    clips_list = list(clips)
    if not clips_list:
        raise ValueError("No clips to concatenate")

    output.parent.mkdir(parents=True, exist_ok=True)

    # 创建 concat 文件列表
    concat_file = output.parent / f"{output.stem}_concat.txt"
    concat_content = "\n".join([f"file '{clip.as_posix()}'" for clip in clips_list])
    concat_file.write_text(concat_content, encoding="utf-8")

    try:
        if use_stream_copy:
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_file.as_posix(),
                "-c",
                "copy",
                output.as_posix(),
            ]
        else:
            # 重编码模式（处理不同编码格式的片段）
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_file.as_posix(),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                output.as_posix(),
            ]

        logger.info(
            "video.concat",
            clip_count=len(clips_list),
            output=output.name,
            stream_copy=use_stream_copy,
        )

        run_ffmpeg(cmd, description="concat videos")

        return output

    finally:
        # 清理临时文件
        concat_file.unlink(missing_ok=True)


def concat_with_audio(
    video: Path,
    audio: Path,
    output: Path,
    *,
    audio_start_ms: int = 0,
    audio_duration_ms: int | None = None,
) -> Path:
    """将视频与音频合并。

    可选择裁剪音频到指定时间范围。

    Args:
        video: 视频文件路径
        audio: 音频文件路径
        output: 输出文件路径
        audio_start_ms: 音频起始时间（毫秒）
        audio_duration_ms: 音频时长（毫秒），None 表示不裁剪

    Returns:
        输出文件路径
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video.as_posix(),
    ]

    # 音频裁剪参数
    if audio_start_ms > 0 or audio_duration_ms:
        if audio_start_ms > 0:
            cmd.extend(["-ss", f"{audio_start_ms / 1000:.3f}"])
        if audio_duration_ms:
            cmd.extend(["-t", f"{audio_duration_ms / 1000:.3f}"])

    cmd.extend(
        [
            "-i",
            audio.as_posix(),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            output.as_posix(),
        ]
    )

    logger.info(
        "video.concat_with_audio",
        video=video.name,
        audio=audio.name,
        audio_start_ms=audio_start_ms,
        audio_duration_ms=audio_duration_ms,
    )

    run_ffmpeg(cmd, description="concat with audio")

    return output


def create_concat_file(clips: Iterable[Path], output_path: Path) -> Path:
    """创建 FFmpeg concat 文件列表。

    Args:
        clips: 视频片段路径列表
        output_path: 输出文件路径

    Returns:
        concat 文件路径
    """
    clips_list = list(clips)
    content = "\n".join([f"file '{clip.as_posix()}'" for clip in clips_list])
    output_path.write_text(content, encoding="utf-8")
    return output_path

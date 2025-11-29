"""视频片段精确裁剪模块

使用 FFmpeg 实现毫秒级精度的视频裁剪，支持：
- Output seeking 精确定位
- 循环模式处理超长裁剪
- 边界检查和自动调整
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import structlog

from src.video.utils import get_video_duration_ms, verify_video_streams

logger = structlog.get_logger(__name__)


def cut_clip(
    source: str | Path,
    start_ms: int,
    end_ms: int,
    target: Path,
    *,
    preset: str = "ultrafast",
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    audio_bitrate: str = "128k",
) -> bool:
    """精确裁剪视频片段。

    使用 output seeking + 重编码确保毫秒级精度：
    1. -ss 放在 -i 之后实现精确定位
    2. libx264 重编码确保输出时长精确
    3. 自动处理边界情况

    Args:
        source: 源视频文件路径或 URL
        start_ms: 起始时间（毫秒）
        end_ms: 结束时间（毫秒）
        target: 输出文件路径
        preset: FFmpeg 编码预设，默认 "ultrafast"
        video_codec: 视频编码器，默认 "libx264"
        audio_codec: 音频编码器，默认 "aac"
        audio_bitrate: 音频比特率，默认 "128k"

    Returns:
        是否成功

    Example:
        >>> success = cut_clip("video.mp4", 5000, 10000, Path("clip.mp4"))
        >>> if success:
        ...     print("裁剪成功")
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    start_ms = max(0, start_ms)
    end_ms = max(end_ms, start_ms + 500)
    duration = max((end_ms - start_ms) / 1000.0, 0.5)

    source_str = str(source)

    # 边界检查
    source_duration_ms = get_video_duration_ms(source_str)
    if source_duration_ms:
        # 起始时间超出视频时长，使用循环模式
        if start_ms >= source_duration_ms:
            logger.warning(
                "clip_cutter.out_of_bounds",
                start_ms=start_ms,
                source_duration_ms=source_duration_ms,
            )
            return cut_clip_with_loop(source_str, duration, target, preset=preset)

        # 结束时间超出，使用循环模式保证时长
        if end_ms > source_duration_ms:
            logger.warning(
                "clip_cutter.exceeds_duration",
                start_ms=start_ms,
                end_ms=end_ms,
                source_duration_ms=source_duration_ms,
            )
            return cut_clip_with_loop(source_str, duration, target, preset=preset)

    # 精确裁剪命令
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        source_str,
        "-ss",
        f"{start_ms / 1000:.3f}",  # output seeking
        "-t",
        f"{duration:.3f}",
        "-c:v",
        video_codec,
        "-preset",
        preset,
        "-c:a",
        audio_codec,
        "-b:a",
        audio_bitrate,
        target.as_posix(),
    ]

    try:
        logger.info(
            "clip_cutter.cutting",
            source=source_str,
            start_ms=start_ms,
            end_ms=end_ms,
            duration=duration,
            target=target.name,
        )
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if target.exists() and verify_video_streams(target):
            return True

        logger.warning("clip_cutter.no_valid_streams", target=target.as_posix())
        if target.exists():
            target.unlink()

    except FileNotFoundError:
        logger.error("clip_cutter.ffmpeg_not_found")
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr if exc.stderr else ""
        error_lines = stderr.strip().split("\n")[-5:] if stderr else []
        logger.error(
            "clip_cutter.failed",
            returncode=exc.returncode,
            errors=error_lines,
        )

    return False


def cut_clip_with_loop(
    source: str | Path,
    duration: float,
    target: Path,
    *,
    preset: str = "ultrafast",
) -> bool:
    """使用循环模式裁剪视频。

    当需要的时长超过源视频时长时，使用 -stream_loop 循环输入。

    Args:
        source: 源视频文件路径或 URL
        duration: 需要的时长（秒）
        target: 输出文件路径
        preset: FFmpeg 编码预设

    Returns:
        是否成功
    """
    target.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",  # 无限循环
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        target.as_posix(),
    ]

    try:
        logger.info(
            "clip_cutter.cutting_with_loop",
            source=str(source),
            duration=duration,
            target=target.name,
        )
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if target.exists() and verify_video_streams(target):
            return True

        if target.exists():
            target.unlink()

    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr if exc.stderr else ""
        error_lines = stderr.strip().split("\n")[-5:] if stderr else []
        logger.error(
            "clip_cutter.loop_failed",
            returncode=exc.returncode,
            errors=error_lines,
        )

    return False


def cut_clip_stream_copy(
    source: str | Path,
    start_ms: int,
    end_ms: int,
    target: Path,
) -> bool:
    """使用流复制模式裁剪（快速但不精确）。

    适用于不需要精确时长的场景，速度更快。

    Args:
        source: 源视频文件路径或 URL
        start_ms: 起始时间（毫秒）
        end_ms: 结束时间（毫秒）
        target: 输出文件路径

    Returns:
        是否成功
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    duration = (end_ms - start_ms) / 1000.0

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_ms / 1000:.3f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.3f}",
        "-c",
        "copy",  # 流复制，不重编码
        target.as_posix(),
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return target.exists()
    except subprocess.CalledProcessError:
        return False

"""视频处理工具函数"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import decord  # type: ignore[import-not-found]
import numpy as np
import structlog

logger = structlog.get_logger(__name__)


def extract_frames(video_path: str | Path, frame_indices: list[int]) -> np.ndarray:
    """从视频中提取指定帧。

    Args:
        video_path: 视频文件路径
        frame_indices: 帧索引列表

    Returns:
        numpy 数组 (N, H, W, C)，dtype=uint8

    Example:
        >>> frames = extract_frames("video.mp4", [0, 30, 60])
        >>> print(frames.shape)  # (3, 1080, 1920, 3)
    """
    try:
        vr = decord.VideoReader(str(video_path), ctx=decord.cpu(0))
        frames = vr.get_batch(frame_indices).asnumpy()
        return np.asarray(frames)
    except Exception as e:
        logger.error("video.extract_frames_failed", error=str(e), path=str(video_path))
        return np.array([])


def get_video_metadata(video_path: str | Path) -> Optional[dict]:
    """获取视频元信息。

    Args:
        video_path: 视频文件路径

    Returns:
        包含以下字段的字典，或 None（如果失败）：
        - total_frames: 总帧数
        - fps: 帧率
        - duration: 时长（秒）
    """
    try:
        vr = decord.VideoReader(str(video_path), ctx=decord.cpu(0))
        total_frames = len(vr)
        fps = vr.get_avg_fps()
        return {
            "total_frames": total_frames,
            "fps": fps,
            "duration": total_frames / fps,
        }
    except Exception as e:
        logger.error("video.get_metadata_failed", error=str(e), path=str(video_path))
        return None


def get_video_duration_ms(video_path: str | Path) -> Optional[int]:
    """使用 ffprobe 获取视频时长（毫秒）。

    Args:
        video_path: 视频文件或 URL 路径

    Returns:
        时长（毫秒），或 None（如果失败）
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()) * 1000)
        return None
    except Exception as e:
        logger.error("video.get_duration_failed", error=str(e), path=str(video_path))
        return None


def verify_video_streams(video_path: Path) -> bool:
    """验证视频文件是否包含有效的视频流。

    Args:
        video_path: 视频文件路径

    Returns:
        True 如果文件包含有效的视频流
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path.as_posix(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and "video" in result.stdout.strip()
    except Exception as e:
        logger.error("video.verify_streams_failed", error=str(e), path=str(video_path))
        return False


def format_timestamp(seconds: float) -> str:
    """将秒数转换为 MM:SS 格式。

    Args:
        seconds: 秒数

    Returns:
        MM:SS 格式的时间戳
    """
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def format_srt_timestamp(ms: int) -> str:
    """将毫秒转换为 SRT 时间戳格式。

    Args:
        ms: 毫秒数

    Returns:
        HH:MM:SS,mmm 格式的时间戳
    """
    seconds, milli = divmod(ms, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{sec:02d},{milli:03d}"


def run_ffmpeg(cmd: list[str], description: str = "") -> None:
    """执行 FFmpeg 命令。

    Args:
        cmd: FFmpeg 命令行参数列表
        description: 命令描述（用于日志）

    Raises:
        RuntimeError: 如果 FFmpeg 命令执行失败
    """
    try:
        logger.info("video.ffmpeg", cmd=" ".join(cmd), description=description)
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        logger.error("video.ffmpeg_not_found", cmd=cmd, error=str(exc))
        raise RuntimeError(f"FFmpeg not found. Please install ffmpeg: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        stderr_output = exc.stderr if exc.stderr else "No error output"
        logger.error(
            "video.ffmpeg_failed",
            returncode=exc.returncode,
            cmd=cmd,
            stderr=stderr_output[:500],
        )
        raise RuntimeError(
            f"FFmpeg command failed with return code {exc.returncode}.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Error: {stderr_output}"
        ) from exc

"""字幕烧录模块

使用 FFmpeg subtitles 滤镜将字幕渲染到视频画面上。
"""

from __future__ import annotations

from pathlib import Path

import structlog

from src.video.utils import run_ffmpeg

logger = structlog.get_logger(__name__)


def burn_subtitles(
    video: Path,
    subtitle: Path,
    output: Path,
    *,
    font_name: str = "Arial",
    font_size: int = 24,
    primary_color: str = "&HFFFFFF",
    outline_color: str = "&H000000",
    outline_width: int = 2,
    margin_v: int = 50,
    preset: str = "fast",
    crf: int = 23,
) -> Path:
    """将字幕烧录到视频中。

    Args:
        video: 输入视频文件路径
        subtitle: SRT 字幕文件路径
        output: 输出视频文件路径
        font_name: 字体名称，默认 Arial
        font_size: 字体大小，默认 24
        primary_color: 文字颜色（ASS 格式），默认白色
        outline_color: 边框颜色（ASS 格式），默认黑色
        outline_width: 边框宽度，默认 2
        margin_v: 底部边距（像素），默认 50
        preset: FFmpeg 编码预设，默认 "fast"
        crf: 视频质量（0-51，越小越好），默认 23

    Returns:
        输出文件路径

    Example:
        >>> output = burn_subtitles(
        ...     Path("video.mp4"),
        ...     Path("subtitle.srt"),
        ...     Path("output.mp4")
        ... )
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    # 处理路径中的特殊字符
    subtitle_path_str = subtitle.as_posix().replace("\\", "/").replace(":", "\\:")

    # 构建 force_style 参数
    force_style = (
        f"FontName={font_name},"
        f"FontSize={font_size},"
        f"PrimaryColour={primary_color},"
        f"OutlineColour={outline_color},"
        f"Outline={outline_width},"
        f"MarginV={margin_v}"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video.as_posix(),
        "-vf",
        f"subtitles={subtitle_path_str}:force_style='{force_style}'",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-c:a",
        "copy",
        output.as_posix(),
    ]

    logger.info(
        "video.burn_subtitles",
        video=video.name,
        subtitle=subtitle.name,
        output=output.name,
    )

    run_ffmpeg(cmd, description="burn subtitles")

    logger.info(
        "video.subtitles_burned",
        output_size=output.stat().st_size if output.exists() else 0,
    )

    return output


def burn_subtitles_ass(
    video: Path,
    subtitle: Path,
    output: Path,
    *,
    preset: str = "fast",
    crf: int = 23,
) -> Path:
    """使用 ASS 字幕烧录到视频中。

    ASS 格式字幕支持更丰富的样式，样式已包含在字幕文件中。

    Args:
        video: 输入视频文件路径
        subtitle: ASS 字幕文件路径
        output: 输出视频文件路径
        preset: FFmpeg 编码预设
        crf: 视频质量

    Returns:
        输出文件路径
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    subtitle_path_str = subtitle.as_posix().replace("\\", "/").replace(":", "\\:")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video.as_posix(),
        "-vf",
        f"ass={subtitle_path_str}",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-c:a",
        "copy",
        output.as_posix(),
    ]

    logger.info(
        "video.burn_subtitles_ass",
        video=video.name,
        subtitle=subtitle.name,
    )

    run_ffmpeg(cmd, description="burn ASS subtitles")

    return output

"""字幕生成器：从歌词行生成 SRT 字幕文件。"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import structlog

logger = structlog.get_logger(__name__)


class LyricLine:
    """歌词行数据结构。"""

    def __init__(self, text: str, start_ms: int, end_ms: int):
        self.text = text
        self.start_ms = start_ms
        self.end_ms = end_ms


def _format_srt_timestamp(ms: int) -> str:
    """将毫秒转换为 SRT 时间戳格式 (HH:MM:SS,mmm)。

    示例:
        0 -> "00:00:00,000"
        1500 -> "00:00:01,500"
        90000 -> "00:01:30,000"
    """
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def generate_srt(lyric_lines: Sequence[LyricLine], output_path: Path) -> None:
    """生成 SRT 字幕文件。

    Args:
        lyric_lines: 歌词行序列
        output_path: 输出的 SRT 文件路径
    """
    logger.info(
        "subtitle_generator.generate_srt",
        line_count=len(lyric_lines),
        output=output_path.as_posix(),
    )

    srt_content = []

    for idx, line in enumerate(lyric_lines, start=1):
        # SRT 格式：
        # 1
        # 00:00:00,000 --> 00:00:03,020
        # 让宇宙听见怒吼
        # (空行)

        start_time = _format_srt_timestamp(line.start_ms)
        end_time = _format_srt_timestamp(line.end_ms)

        srt_content.append(f"{idx}")
        srt_content.append(f"{start_time} --> {end_time}")
        srt_content.append(line.text)
        srt_content.append("")  # 空行分隔

    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(srt_content), encoding="utf-8")

    logger.info(
        "subtitle_generator.srt_generated",
        file_size=output_path.stat().st_size,
        line_count=len(lyric_lines),
        message=f"SRT 字幕文件已生成: {output_path}",
    )


def generate_ass(
    lyric_lines: Sequence[LyricLine],
    output_path: Path,
    font_name: str = "Arial",
    font_size: int = 24,
    primary_color: str = "&HFFFFFF",  # 白色
    outline_color: str = "&H000000",  # 黑色边框
) -> None:
    """生成 ASS 字幕文件（支持更多样式）。

    Args:
        lyric_lines: 歌词行序列
        output_path: 输出的 ASS 文件路径
        font_name: 字体名称
        font_size: 字体大小
        primary_color: 主颜色 (ASS 颜色格式)
        outline_color: 边框颜色
    """
    logger.info(
        "subtitle_generator.generate_ass",
        line_count=len(lyric_lines),
        output=output_path.as_posix(),
    )

    # ASS 文件头
    ass_header = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000,{outline_color},&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    ass_content = [ass_header.strip()]

    for line in lyric_lines:
        # ASS 时间戳格式: H:MM:SS.cc (百分之一秒)
        start_time = _format_ass_timestamp(line.start_ms)
        end_time = _format_ass_timestamp(line.end_ms)

        # 转义文本
        text = line.text.replace("\n", "\\N")

        ass_content.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}")

    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(ass_content), encoding="utf-8")

    logger.info(
        "subtitle_generator.ass_generated",
        file_size=output_path.stat().st_size,
        line_count=len(lyric_lines),
        message=f"ASS 字幕文件已生成: {output_path}",
    )


def _format_ass_timestamp(ms: int) -> str:
    """将毫秒转换为 ASS 时间戳格式 (H:MM:SS.cc)。

    示例:
        0 -> "0:00:00.00"
        1500 -> "0:00:01.50"
        90000 -> "0:01:30.00"
    """
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    centiseconds = (ms % 1000) // 10

    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"

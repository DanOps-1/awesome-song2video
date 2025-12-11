"""字幕生成模块

支持生成 SRT 和 ASS 格式字幕文件。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SubtitleLine:
    """字幕行数据结构"""

    text: str
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        """字幕时长（毫秒）"""
        return self.end_ms - self.start_ms


# 兼容旧代码的别名
LyricLine = SubtitleLine


class HasTimestamp(Protocol):
    """具有时间戳的对象协议"""

    text: str
    start_ms: int
    end_ms: int


def format_srt_timestamp(ms: int) -> str:
    """将毫秒转换为 SRT 时间戳格式 (HH:MM:SS,mmm)。

    Args:
        ms: 毫秒数

    Returns:
        SRT 格式时间戳

    Example:
        >>> format_srt_timestamp(1500)
        '00:00:01,500'
    """
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milliseconds = ms % 1000

    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def format_ass_timestamp(ms: int) -> str:
    """将毫秒转换为 ASS 时间戳格式 (H:MM:SS.cc)。

    Args:
        ms: 毫秒数

    Returns:
        ASS 格式时间戳

    Example:
        >>> format_ass_timestamp(1500)
        '0:00:01.50'
    """
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    centiseconds = (ms % 1000) // 10

    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def generate_srt(
    lines: Sequence[SubtitleLine] | Sequence[HasTimestamp],
    output_path: Path,
    *,
    offset_ms: int = 0,
) -> Path:
    """生成 SRT 字幕文件。

    Args:
        lines: 字幕行序列
        output_path: 输出文件路径
        offset_ms: 时间偏移量（毫秒），所有时间戳减去此值

    Returns:
        输出文件路径

    Example:
        >>> lines = [SubtitleLine("Hello", 0, 2000), SubtitleLine("World", 2000, 4000)]
        >>> generate_srt(lines, Path("subtitle.srt"))
    """
    logger.info(
        "subtitle.generate_srt",
        line_count=len(lines),
        output=output_path.as_posix(),
        offset_ms=offset_ms,
    )

    srt_content = []

    for idx, line in enumerate(lines, start=1):
        start_ms = max(0, line.start_ms - offset_ms)
        end_ms = max(0, line.end_ms - offset_ms)

        start_time = format_srt_timestamp(start_ms)
        end_time = format_srt_timestamp(end_ms)

        srt_content.append(f"{idx}")
        srt_content.append(f"{start_time} --> {end_time}")
        srt_content.append(line.text)
        srt_content.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(srt_content), encoding="utf-8")

    logger.info(
        "subtitle.srt_generated",
        file_size=output_path.stat().st_size,
        line_count=len(lines),
    )

    return output_path


def generate_ass(
    lines: Sequence[SubtitleLine] | Sequence[HasTimestamp],
    output_path: Path,
    *,
    offset_ms: int = 0,
    font_name: str = "Arial",
    font_size: int = 24,
    primary_color: str = "&HFFFFFF",
    outline_color: str = "&H000000",
    resolution: tuple[int, int] = (1920, 1080),
) -> Path:
    """生成 ASS 字幕文件（支持更多样式）。

    Args:
        lines: 字幕行序列
        output_path: 输出文件路径
        offset_ms: 时间偏移量（毫秒）
        font_name: 字体名称
        font_size: 字体大小
        primary_color: 主颜色（ASS 颜色格式）
        outline_color: 边框颜色
        resolution: 视频分辨率 (width, height)

    Returns:
        输出文件路径
    """
    logger.info(
        "subtitle.generate_ass",
        line_count=len(lines),
        output=output_path.as_posix(),
    )

    res_x, res_y = resolution

    # ASS 文件头
    ass_header = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: {res_x}
PlayResY: {res_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000,{outline_color},&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""

    ass_content = [ass_header]

    for line in lines:
        start_ms = max(0, line.start_ms - offset_ms)
        end_ms = max(0, line.end_ms - offset_ms)

        start_time = format_ass_timestamp(start_ms)
        end_time = format_ass_timestamp(end_ms)

        # 转义文本中的换行符
        text = line.text.replace("\n", "\\N")

        ass_content.append(
            f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(ass_content), encoding="utf-8")

    logger.info(
        "subtitle.ass_generated",
        file_size=output_path.stat().st_size,
        line_count=len(lines),
    )

    return output_path


def parse_srt(srt_path: Path) -> list[SubtitleLine]:
    """解析 SRT 字幕文件。

    Args:
        srt_path: SRT 文件路径

    Returns:
        字幕行列表
    """
    content = srt_path.read_text(encoding="utf-8")
    lines = []
    blocks = content.strip().split("\n\n")

    for block in blocks:
        parts = block.strip().split("\n")
        if len(parts) >= 3:
            # 解析时间戳行
            time_line = parts[1]
            start_str, end_str = time_line.split(" --> ")
            start_ms = _parse_srt_timestamp(start_str.strip())
            end_ms = _parse_srt_timestamp(end_str.strip())
            text = "\n".join(parts[2:])
            lines.append(SubtitleLine(text=text, start_ms=start_ms, end_ms=end_ms))

    return lines


def _parse_srt_timestamp(timestamp: str) -> int:
    """解析 SRT 时间戳为毫秒。

    Args:
        timestamp: SRT 格式时间戳 (HH:MM:SS,mmm)

    Returns:
        毫秒数
    """
    time_part, ms_part = timestamp.replace(",", ".").split(".")
    h, m, s = time_part.split(":")
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms_part)

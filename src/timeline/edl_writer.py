"""EDL（Edit Decision List）写入器

将时间线导出为可用于视频渲染的 EDL 格式。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from src.timeline.models import Timeline, RenderLine


RESOLUTION_MAP = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (854, 480),
}


class EDLWriter:
    """EDL 写入器"""

    def __init__(
        self,
        resolution: str = "1080p",
        frame_rate: int = 30,
    ):
        """初始化 EDL 写入器

        Args:
            resolution: 分辨率（1080p, 720p, 480p）
            frame_rate: 帧率
        """
        if resolution not in RESOLUTION_MAP:
            raise ValueError(f"Unsupported resolution: {resolution}")

        self.resolution = resolution
        self.frame_rate = frame_rate

    def timeline_to_render_lines(
        self,
        timeline: Timeline,
    ) -> List[RenderLine]:
        """将时间线转换为渲染行列表"""
        return [
            RenderLine.from_segment(segment)
            for segment in timeline.segments
        ]

    def write_edl(
        self,
        timeline: Timeline,
        output_path: Path,
    ) -> None:
        """写入 EDL 文件

        Args:
            timeline: 时间线对象
            output_path: 输出文件路径
        """
        render_lines = self.timeline_to_render_lines(timeline)

        # 序列化时排除 candidates 字段
        serialized_lines = [
            {
                "source_video_id": line.source_video_id,
                "start_time_ms": line.start_time_ms,
                "end_time_ms": line.end_time_ms,
                "lyrics": line.lyrics,
                "lyric_start_ms": line.lyric_start_ms,
                "lyric_end_ms": line.lyric_end_ms,
            }
            for line in render_lines
        ]

        data = {
            "resolution": self.resolution,
            "frame_rate": self.frame_rate,
            "audio_duration_ms": timeline.audio_duration_ms,
            "lines": serialized_lines,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def load_edl(self, edl_path: Path) -> dict:
        """加载 EDL 文件

        Args:
            edl_path: EDL 文件路径

        Returns:
            EDL 数据字典
        """
        return json.loads(edl_path.read_text())

    def build_ffmpeg_filter(
        self,
        render_lines: List[RenderLine],
    ) -> str:
        """构建 FFmpeg filter 命令

        Args:
            render_lines: 渲染行列表

        Returns:
            FFmpeg filter 字符串
        """
        width, height = RESOLUTION_MAP[self.resolution]
        n = len(render_lines)

        concat_inputs = "".join([f"[{i}:v:0][{i}:a:0]" for i in range(n)])
        filter_cmd = (
            f'-filter_complex "{concat_inputs}concat=n={n}:v=1:a=1'
            f',scale={width}:{height}"'
        )

        return filter_cmd

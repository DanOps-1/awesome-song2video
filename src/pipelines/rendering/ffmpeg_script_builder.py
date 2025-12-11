"""用于生成 FFmpeg filtergraph 与歌词字幕脚本。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


RESOLUTION_MAP = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
}


@dataclass
class VideoCandidate:
    """单个候选视频片段。"""

    video_id: str
    start_ms: int
    end_ms: int
    score: float


@dataclass
class RenderLine:
    source_video_id: str  # 主要候选（第一个）
    start_time_ms: int
    end_time_ms: int
    lyrics: str
    lyric_start_ms: int
    lyric_end_ms: int
    candidates: list[VideoCandidate] | None = None  # 所有候选片段（包括第一个）


class FFMpegScriptBuilder:
    def __init__(self, resolution: str, frame_rate: int) -> None:
        if resolution not in RESOLUTION_MAP:
            raise ValueError("unsupported resolution")
        self.resolution = resolution
        self.frame_rate = frame_rate

    def build_script(self, lines: Iterable[RenderLine]) -> str:
        width, height = RESOLUTION_MAP[self.resolution]
        concat_inputs = "".join([f"[{idx}:v:0][{idx}:a:0]" for idx, _ in enumerate(lines)])
        script = (
            f'-filter_complex "{concat_inputs}concat=n={len(list(lines))}:v=1:a=1'
            f',scale={width}:{height}"'
        )
        return script

    def write_edl(self, lines: Iterable[RenderLine], output_path: Path) -> None:
        # 序列化时排除 candidates 字段（仅用于运行时回退）
        serialized_lines = [
            {
                "source_video_id": line.source_video_id,
                "start_time_ms": line.start_time_ms,
                "end_time_ms": line.end_time_ms,
                "lyrics": line.lyrics,
                "lyric_start_ms": line.lyric_start_ms,
                "lyric_end_ms": line.lyric_end_ms,
            }
            for line in lines
        ]
        data = {
            "resolution": self.resolution,
            "frame_rate": self.frame_rate,
            "lines": serialized_lines,
        }
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

#!/usr/bin/env python3
"""生成默认的占位视频片段（黑屏 + beep）。"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 3 秒黑屏 + beep 的占位视频片段")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("media/fallback/clip_placeholder.mp4"),
        help="输出文件路径（默认 media/fallback/clip_placeholder.mp4）",
    )
    parser.add_argument("--duration", type=float, default=3.0, help="片段时长（秒）")
    parser.add_argument("--frequency", type=int, default=500, help="提示音频率（Hz）")
    parser.add_argument("--resolution", type=str, default="1920x1080", help="画面分辨率，如 1920x1080")
    return parser


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def create_placeholder(path: Path, duration: float, frequency: int, resolution: str) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={resolution}:d={duration}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={frequency}:duration={duration}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        path.as_posix(),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    ensure_parent(args.output)
    create_placeholder(args.output, args.duration, args.frequency, args.resolution)
    print(f"占位片段已生成：{args.output}")


if __name__ == "__main__":
    main()

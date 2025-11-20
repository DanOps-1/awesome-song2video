#!/usr/bin/env python
"""分析时间戳重叠情况。"""

import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twelvelabs import TwelveLabs
from src.infra.config.settings import get_settings


def check_overlap(start1: float, end1: float, start2: float, end2: float) -> tuple[bool, float]:
    """检查两个时间段是否重叠，返回 (是否重叠, 重叠秒数)。"""
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    overlap_duration = max(0, overlap_end - overlap_start)
    return overlap_duration > 0, overlap_duration


def main() -> None:
    settings = get_settings()
    client = TwelveLabs(api_key=settings.tl_api_key)

    query = "夜晚的城市灯光"

    print("=" * 80)
    print(f"查询: {query}")
    print("=" * 80)

    search_params = {
        "index_id": settings.tl_index_id,
        "query_text": query,
        "search_options": ["visual", "audio"],
        "group_by": "clip",
        "page_limit": 20,
    }

    pager = client.search.query(**search_params)

    # 按 video_id 分组
    videos = defaultdict(list)
    for idx, item in enumerate(pager):
        video_id = getattr(item, "video_id", None)
        start = getattr(item, "start", None)
        end = getattr(item, "end", None)
        rank = getattr(item, "rank", None)

        videos[video_id].append({
            "rank": rank,
            "start": start,
            "end": end,
        })

        if idx >= 19:
            break

    # 分析每个视频的片段
    print("\n重叠分析:")
    print("=" * 80)

    for video_id, clips in videos.items():
        if len(clips) < 2:
            continue  # 只有一个片段，跳过

        print(f"\nvideo_id: {video_id}")
        print(f"片段数: {len(clips)}")
        print("-" * 80)

        # 按 start 时间排序
        sorted_clips = sorted(clips, key=lambda c: c["start"])

        # 检查相邻片段的重叠
        for i in range(len(sorted_clips)):
            clip1 = sorted_clips[i]
            print(f"  [{i+1}] Rank {clip1['rank']}: {clip1['start']:.2f}s - {clip1['end']:.2f}s")

        print()
        for i in range(len(sorted_clips) - 1):
            clip1 = sorted_clips[i]
            clip2 = sorted_clips[i + 1]

            has_overlap, overlap_duration = check_overlap(
                clip1["start"], clip1["end"],
                clip2["start"], clip2["end"]
            )

            gap = clip2["start"] - clip1["end"]

            if has_overlap:
                print(f"  ⚠️  片段 {i+1} 和 {i+2} 重叠: {overlap_duration:.2f} 秒")
            elif gap == 0:
                print(f"  ✅ 片段 {i+1} 和 {i+2} 完美相接（无间隙）")
            elif gap > 0:
                print(f"  ➡️  片段 {i+1} 和 {i+2} 有间隙: {gap:.2f} 秒")
            else:
                print(f"  ❌ 片段顺序异常: gap={gap:.2f} 秒")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""调试重复视频问题 - 使用实际查询。"""

import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twelvelabs import TwelveLabs
from src.infra.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    client = TwelveLabs(api_key=settings.tl_api_key)

    # 使用多个测试查询
    queries = [
        "夜晚的城市灯光",
        "人在奔跑",
        "美丽的风景",
        "dancing people",
        "sunset ocean",
    ]

    for query in queries:
        print("\n" + "=" * 80)
        print(f"查询: {query}")
        print("=" * 80)

        search_params = {
            "index_id": settings.tl_index_id,
            "query_text": query,
            "search_options": ["visual", "audio"],
            "group_by": "clip",
            "page_limit": 10,  # 获取更多结果以观察重复模式
        }

        pager = client.search.query(**search_params)

        video_ids = []
        video_timestamps = []  # 记录 (video_id, start, end) 组合

        for idx, item in enumerate(pager):
            video_id = getattr(item, "video_id", None)
            start = getattr(item, "start", None)
            end = getattr(item, "end", None)
            rank = getattr(item, "rank", None)

            video_ids.append(video_id)
            video_timestamps.append((video_id, start, end))

            print(f"\n[{idx + 1}] video_id: {video_id}")
            print(f"    rank: {rank}")
            print(f"    start: {start} s")
            print(f"    end: {end} s")
            print(f"    duration: {end - start if start and end else 'N/A'} s")

            if idx >= 9:  # 只看前10个
                break

        # 统计重复情况
        print("\n" + "-" * 80)
        print("重复分析:")
        print("-" * 80)

        video_id_counts = Counter(video_ids)
        duplicate_videos = {vid: count for vid, count in video_id_counts.items() if count > 1}

        if duplicate_videos:
            print(f"\n⚠️  发现重复的 video_id:")
            for vid, count in duplicate_videos.items():
                print(f"  - {vid}: 出现 {count} 次")
                # 显示这个视频的所有时间戳
                matching_timestamps = [
                    (start, end) for v, start, end in video_timestamps if v == vid
                ]
                print(f"    时间戳: {matching_timestamps}")
        else:
            print("✅ 没有重复的 video_id")

        # 检查是否有完全相同的 (video_id, start, end) 组合
        timestamp_counts = Counter(video_timestamps)
        duplicate_timestamps = {ts: count for ts, count in timestamp_counts.items() if count > 1}

        if duplicate_timestamps:
            print(f"\n⚠️  发现完全相同的片段 (video_id + 时间戳):")
            for (vid, start, end), count in duplicate_timestamps.items():
                print(f"  - {vid} [{start}-{end}]: 出现 {count} 次")
        else:
            print("✅ 没有完全相同的片段")


if __name__ == "__main__":
    main()

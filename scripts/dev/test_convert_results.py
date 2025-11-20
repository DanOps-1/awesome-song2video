#!/usr/bin/env python
"""测试 _convert_results 方法的实际行为。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twelvelabs import TwelveLabs
from src.infra.config.settings import get_settings
from src.services.matching.twelvelabs_client import TwelveLabsClient


def main() -> None:
    settings = get_settings()
    sdk_client = TwelveLabs(api_key=settings.tl_api_key)
    our_client = TwelveLabsClient()

    query = "夜晚的城市灯光"
    limit = 10

    print("=" * 80)
    print(f"查询: {query}")
    print(f"限制: {limit} 个结果")
    print("=" * 80)

    search_params = {
        "index_id": settings.tl_index_id,
        "query_text": query,
        "search_options": ["visual", "audio"],
        "group_by": "clip",
        "page_limit": 20,  # 多获取一些原始结果
    }

    pager = sdk_client.search.query(**search_params)

    print("\n调用 _convert_results 方法...")
    results = our_client._convert_results(pager, limit=limit)

    print(f"\n返回结果数: {len(results)}")
    print("=" * 80)

    for idx, result in enumerate(results):
        print(f"\n[{idx + 1}] id: {result['id']}")
        print(f"    video_id: {result['video_id']}")
        print(f"    start: {result['start']} ms")
        print(f"    end: {result['end']} ms")
        print(f"    duration: {(result['end'] - result['start']) / 1000:.2f} s")
        print(f"    score: {result['score']}")
        print(f"    rank: {result.get('rank', 'N/A')}")

    # 检查重复
    print("\n" + "=" * 80)
    print("重复检测:")
    print("=" * 80)

    video_timestamps = {}
    for result in results:
        video_id = result["video_id"]
        start = result["start"]
        end = result["end"]

        if video_id not in video_timestamps:
            video_timestamps[video_id] = []
        video_timestamps[video_id].append((start, end))

    duplicates_found = False
    for video_id, timestamps in video_timestamps.items():
        if len(timestamps) > 1:
            duplicates_found = True
            print(f"\nvideo_id: {video_id}")
            print(f"  出现次数: {len(timestamps)}")
            for i, (start, end) in enumerate(timestamps, 1):
                print(f"  [{i}] {start}-{end} ms ({(end-start)/1000:.2f}s)")

    if not duplicates_found:
        print("\n✅ 没有重复的 video_id")


if __name__ == "__main__":
    main()

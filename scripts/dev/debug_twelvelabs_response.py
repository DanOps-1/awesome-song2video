#!/usr/bin/env python
"""调试 TwelveLabs API 响应格式。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twelvelabs import TwelveLabs
from src.infra.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    client = TwelveLabs(api_key=settings.tl_api_key)

    query = "A person running"

    print("=" * 80)
    print(f"查询: {query}")
    print("=" * 80)

    # 执行搜索
    search_params = {
        "index_id": settings.tl_index_id,
        "query_text": query,
        "search_options": ["visual", "audio"],
        "group_by": "clip",
        "page_limit": 5,
    }

    print(f"\n搜索参数: {search_params}")
    print("\n" + "=" * 80)
    print("API 响应:")
    print("=" * 80 + "\n")

    pager = client.search.query(**search_params)

    for idx, item in enumerate(pager):
        print(f"\n{'=' * 40} Item {idx + 1} {'=' * 40}")
        print(f"类型: {type(item)}")
        print(f"video_id: {getattr(item, 'video_id', 'N/A')}")
        print(f"score: {getattr(item, 'score', 'N/A')}")
        print(f"rank: {getattr(item, 'rank', 'N/A')}")
        print(f"start: {getattr(item, 'start', 'N/A')}")
        print(f"end: {getattr(item, 'end', 'N/A')}")

        # 检查 clips 字段
        clips = getattr(item, 'clips', None)
        print(f"clips: {clips}")
        if clips:
            print(f"clips 类型: {type(clips)}")
            print(f"clips 长度: {len(clips) if hasattr(clips, '__len__') else 'N/A'}")
            for clip_idx, clip in enumerate(clips):
                print(f"\n  --- Clip {clip_idx + 1} ---")
                print(f"  类型: {type(clip)}")
                print(f"  video_id: {getattr(clip, 'video_id', 'N/A')}")
                print(f"  start: {getattr(clip, 'start', 'N/A')}")
                print(f"  end: {getattr(clip, 'end', 'N/A')}")
                print(f"  score: {getattr(clip, 'score', 'N/A')}")
                print(f"  rank: {getattr(clip, 'rank', 'N/A')}")

        # 显示所有属性
        print(f"\n所有属性: {dir(item)}")

        if idx >= 2:  # 只看前3个结果
            break

    print("\n" + "=" * 80)
    print("调试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()

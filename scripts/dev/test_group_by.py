#!/usr/bin/env python
"""测试 group_by 参数的实际行为。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twelvelabs import TwelveLabs
from src.infra.config.settings import get_settings


def test_group_by(client: TwelveLabs, index_id: str, query: str, group_by: str) -> None:
    """测试指定的 group_by 参数。"""
    print("\n" + "=" * 80)
    print(f"测试 group_by='{group_by}'")
    print("=" * 80)

    search_params = {
        "index_id": index_id,
        "query_text": query,
        "search_options": ["visual", "audio"],
        "group_by": group_by,
        "page_limit": 5,
    }

    print(f"\n搜索参数: {search_params}\n")

    pager = client.search.query(**search_params)

    for idx, item in enumerate(pager):
        print(f"\n{'─' * 40} Item {idx + 1} {'─' * 40}")
        print(f"类型: {type(item).__name__}")
        print(f"video_id: {getattr(item, 'video_id', 'N/A')}")
        print(f"score: {getattr(item, 'score', 'N/A')}")
        print(f"rank: {getattr(item, 'rank', 'N/A')}")
        print(f"start: {getattr(item, 'start', 'N/A')}")
        print(f"end: {getattr(item, 'end', 'N/A')}")

        # 检查 clips 字段
        clips = getattr(item, 'clips', None)
        print(f"\nclips 字段:")
        print(f"  值: {clips}")
        print(f"  类型: {type(clips) if clips is not None else 'None'}")

        if clips:
            print(f"  长度: {len(clips)}")
            for clip_idx, clip in enumerate(clips[:3]):  # 只显示前3个
                print(f"\n  【Clip {clip_idx + 1}】")
                print(f"    video_id: {getattr(clip, 'video_id', 'N/A')}")
                print(f"    start: {getattr(clip, 'start', 'N/A')}")
                print(f"    end: {getattr(clip, 'end', 'N/A')}")
                print(f"    score: {getattr(clip, 'score', 'N/A')}")
                print(f"    rank: {getattr(clip, 'rank', 'N/A')}")
        else:
            print(f"  → clips 为空或 None")

        # 检查所有可用字段
        all_attrs = [attr for attr in dir(item) if not attr.startswith('_')]
        print(f"\n可用字段: {all_attrs}")

        if idx >= 2:  # 只看前3个结果
            break


def main() -> None:
    settings = get_settings()
    client = TwelveLabs(api_key=settings.tl_api_key)

    query = "A person running"

    print("=" * 80)
    print(f"查询: {query}")
    print(f"索引: {settings.tl_index_id}")
    print("=" * 80)

    # 测试 group_by="clip"
    test_group_by(client, settings.tl_index_id, query, "clip")

    # 测试 group_by="video"
    test_group_by(client, settings.tl_index_id, query, "video")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()

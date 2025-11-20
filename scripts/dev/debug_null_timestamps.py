#!/usr/bin/env python
"""调试 start/end 为 null 的问题。"""

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

    # 从日志中找到的问题查询
    query = "A close-up shot of a digital clock changing numbers in a dimly lit room, cinematic lighting emphasizing the final minute."

    print("=" * 80)
    print(f"查询: {query}")
    print("=" * 80)

    search_params = {
        "index_id": settings.tl_index_id,
        "query_text": query,
        "search_options": ["visual", "audio"],
        "group_by": "clip",
        "page_limit": 10,
    }

    print(f"\n搜索参数: {search_params}\n")

    pager = client.search.query(**search_params)

    null_count = 0
    valid_count = 0

    for idx, item in enumerate(pager):
        video_id = getattr(item, "video_id", None)
        start = getattr(item, "start", None)
        end = getattr(item, "end", None)
        rank = getattr(item, "rank", None)

        if start is None or end is None:
            null_count += 1
            print(f"❌ [{idx+1}] video_id={video_id}, rank={rank}, start={start}, end={end}")
        else:
            valid_count += 1
            print(f"✅ [{idx+1}] video_id={video_id}, rank={rank}, start={start:.2f}s, end={end:.2f}s")

        if idx >= 9:
            break

    print("\n" + "=" * 80)
    print(f"统计: 有效={valid_count}, Null={null_count}")
    print("=" * 80)

    if null_count > 0:
        print("\n⚠️  发现问题：部分结果的 start/end 为 null！")
        print("这会导致代码将其默认为 0，从而产生完全相同的时间戳。")
        print("\n可能原因：")
        print("1. 索引配置问题")
        print("2. 视频上传时未正确处理")
        print("3. TwelveLabs API 在某些情况下不返回时间戳")
        print("4. group_by 参数与索引类型不匹配")


if __name__ == "__main__":
    main()

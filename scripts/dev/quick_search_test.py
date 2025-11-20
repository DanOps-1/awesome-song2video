#!/usr/bin/env python
"""快速搜索测试，生成带 start/end 的日志。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
from src.services.matching.twelvelabs_client import client

async def main():
    # 测试几个不同的查询
    queries = [
        "A close-up shot of a digital clock",  # 之前出问题的查询
        "A person dancing",
        "Beautiful landscape",
    ]

    for query in queries:
        print(f"\n查询: {query}")
        results = await client.search_segments(query, limit=5)
        print(f"结果数: {len(results)}")
        for r in results[:3]:
            print(f"  - video_id={r['video_id']}, start={r['start']}ms, end={r['end']}ms")

if __name__ == "__main__":
    asyncio.run(main())

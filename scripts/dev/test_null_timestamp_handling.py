#!/usr/bin/env python
"""测试 null 时间戳的处理。"""

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.matching.twelvelabs_client import TwelveLabsClient


class MockItem:
    """模拟 TwelveLabs API 返回的 item。"""

    def __init__(self, video_id: str, start: float | None, end: float | None, rank: int):
        self.video_id = video_id
        self.start = start
        self.end = end
        self.rank = rank
        self.score = None
        self.clips = None


def main() -> None:
    client = TwelveLabsClient()

    print("=" * 80)
    print("测试 null 时间戳处理")
    print("=" * 80)

    # 测试数据：包含 null 时间戳和有效时间戳
    mock_items = [
        MockItem("video1", None, None, 1),      # ← null 时间戳，应该被跳过
        MockItem("video2", 10.0, 20.0, 2),      # ← 有效
        MockItem("video3", None, 30.0, 3),      # ← start 为 null，应该被跳过
        MockItem("video4", 40.0, None, 4),      # ← end 为 null，应该被跳过
        MockItem("video5", 50.0, 60.0, 5),      # ← 有效
        MockItem("video2", 70.0, 80.0, 6),      # ← 重复 video_id，应该被跳过
    ]

    print(f"\n输入: {len(mock_items)} 个结果")
    for item in mock_items:
        print(f"  - video_id={item.video_id}, start={item.start}, end={item.end}, rank={item.rank}")

    # 调用 _convert_results
    results = client._convert_results(mock_items, limit=10)

    print(f"\n输出: {len(results)} 个有效结果")
    for idx, result in enumerate(results, 1):
        print(f"  [{idx}] video_id={result['video_id']}, "
              f"start={result['start']}ms, end={result['end']}ms, "
              f"rank={result['rank']}")

    print("\n" + "=" * 80)
    print("预期行为:")
    print("=" * 80)
    print("✅ 应该只有 2 个结果（video2 和 video5）")
    print("✅ video1/3/4 应该被跳过（null 时间戳）")
    print("✅ video2 的第二次出现应该被跳过（重复）")

    print("\n" + "=" * 80)
    print("实际结果:")
    print("=" * 80)

    if len(results) == 2:
        print("✅ 结果数量正确")
    else:
        print(f"❌ 结果数量错误：期望 2，实际 {len(results)}")

    expected_videos = {"video2", "video5"}
    actual_videos = {r["video_id"] for r in results}

    if actual_videos == expected_videos:
        print("✅ 视频 ID 正确")
    else:
        print(f"❌ 视频 ID 错误：期望 {expected_videos}，实际 {actual_videos}")

    # 检查时间戳是否有效
    all_valid = all(r["start"] > 0 and r["end"] > r["start"] for r in results)
    if all_valid:
        print("✅ 所有时间戳都有效")
    else:
        print("❌ 存在无效时间戳")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()

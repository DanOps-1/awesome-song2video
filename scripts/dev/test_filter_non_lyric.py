#!/usr/bin/env python3
"""测试非歌词内容过滤功能。"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.pipelines.matching.timeline_builder import TimelineBuilder


def test_non_lyric_filter():
    """测试非歌词内容识别和过滤。"""
    builder = TimelineBuilder()

    test_cases = [
        # 应该被过滤的（非歌词）
        ("作词 李宗盛", True),
        ("曲 李宗盛", True),
        ("作曲 周杰伦", True),
        ("编曲：林俊杰", True),
        ("演唱 邓紫棋", True),
        ("制作 方大同", True),
        ("Lyrics by John Lennon", True),
        ("Music by Paul McCartney", True),
        ("Composed by Mozart", True),

        # 不应该被过滤的（真实歌词）
        ("让宇宙听见怒吼", False),
        ("咆哮着", False),
        ("燃烧着", False),
        ("我爱你", False),
        ("当城市被笼罩在一片灰色", False),
        ("You are my sunshine", False),
        ("梦想是什么颜色", False),
    ]

    print("🧪 测试非歌词内容过滤功能\n")
    print(f"{'文本':<30} {'预期':<10} {'实际':<10} {'结果'}")
    print("=" * 60)

    passed = 0
    failed = 0

    for text, should_filter in test_cases:
        is_filtered = builder._is_non_lyric_text(text)
        is_correct = is_filtered == should_filter

        if is_correct:
            passed += 1
            result = "✅"
        else:
            failed += 1
            result = "❌"

        expected = "过滤" if should_filter else "保留"
        actual = "过滤" if is_filtered else "保留"

        print(f"{text:<30} {expected:<10} {actual:<10} {result}")

    print("=" * 60)
    print(f"\n📊 测试结果: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("✅ 所有测试通过！")
        return True
    else:
        print(f"❌ {failed} 个测试失败")
        return False


if __name__ == "__main__":
    success = test_non_lyric_filter()
    sys.exit(0 if success else 1)

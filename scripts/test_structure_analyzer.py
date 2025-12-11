#!/usr/bin/env python3
"""测试音乐结构分析功能"""

import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio.structure_analyzer import (
    detect_intro_outro_boundaries,
    merge_intro_outro_lines,
)


def test_structure_analysis():
    """测试《心如止水》的结构分析"""
    print("🎵 测试歌词 intro/outro 检测")
    print("-" * 50)

    # 1. 模拟 API 歌词（心如止水的 LRC 歌词）
    print("\n📝 Step 1: 模拟 API 歌词...")
    lyrics_lines = [
        {"text": "词：Ice Paper", "start_ms": 0, "end_ms": 200},
        {"text": "曲：Ice Paper", "start_ms": 200, "end_ms": 400},
        {"text": "采样：QUIX - Deep Home", "start_ms": 400, "end_ms": 900},
        {"text": "Talking to the moon 放不下的理由", "start_ms": 1100, "end_ms": 4300},
        {"text": "虚度的春夏秋冬拼凑", "start_ms": 4300, "end_ms": 7800},
        {"text": "别让我 后知后觉", "start_ms": 7800, "end_ms": 10500},
        {"text": "还以为心如止水", "start_ms": 10500, "end_ms": 13200},
        # ... 更多歌词
        {"text": "最后一句歌词", "start_ms": 115000, "end_ms": 118000},
    ]

    for line in lyrics_lines[:5]:
        duration = line["end_ms"] - line["start_ms"]
        print(f"  {line['start_ms']/1000:5.2f}s - {line['end_ms']/1000:5.2f}s ({duration}ms) | {line['text']}")
    print("  ...")

    # 2. 检测边界
    print("\n🎯 Step 2: 检测 intro/outro 边界...")
    print("  📝 规则：时长 >= 1秒 的歌词行被认为是真正歌词")
    audio_duration_ms = 123000  # 假设音频时长 123 秒
    intro_end_ms, outro_start_ms = detect_intro_outro_boundaries(
        lyrics_lines=lyrics_lines,
        audio_duration_ms=audio_duration_ms,
    )
    print(f"  Intro 结束: {intro_end_ms}ms ({intro_end_ms/1000:.2f}s)")
    print(f"  Outro 开始: {outro_start_ms}ms ({outro_start_ms/1000:.2f}s)")

    # 3. 合并歌词行
    print("\n🔀 Step 3: 合并 intro/outro 行...")
    merged_lines = merge_intro_outro_lines(
        lyrics_lines=lyrics_lines,
        intro_end_ms=intro_end_ms,
        outro_start_ms=outro_start_ms,
        audio_duration_ms=audio_duration_ms,
    )

    print(f"  原始歌词行数: {len(lyrics_lines)}")
    print(f"  合并后行数: {len(merged_lines)}")
    print("\n  合并后结果:")
    for line in merged_lines:
        is_inst = line.get("is_instrumental", False)
        marker = "🎹" if is_inst else "🎤"
        print(f"    {marker} {line['start_ms']/1000:5.2f}s - {line['end_ms']/1000:5.2f}s | {line['text']}")

    print("\n✅ 测试完成!")


if __name__ == "__main__":
    test_structure_analysis()

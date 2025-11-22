"""测试不同 no_speech_threshold 对两首歌的影响，找到最佳平衡点"""
import os
import sys
from pathlib import Path
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.pipelines.lyrics_ingest.transcriber import transcribe_with_timestamps
from src.infra.config.settings import get_settings


async def test_threshold(audio_path: Path, threshold: float):
    """测试特定阈值下的识别效果"""
    # 临时修改设置
    settings = get_settings()
    original_threshold = settings.whisper_no_speech_threshold
    settings.whisper_no_speech_threshold = threshold

    try:
        segments = await transcribe_with_timestamps(audio_path, language="zh", skip_intro=True)
        return segments
    finally:
        settings.whisper_no_speech_threshold = original_threshold


async def main():
    songs = [
        ("tom.mp3", "林俊杰-江南（无前奏）"),
        ("tom吞噬星空.mp3", "吞噬星空（12秒前奏）"),
    ]

    thresholds = [0.6, 0.7, 0.75, 0.8, 0.85, 0.9]

    results = []

    for song_file, song_name in songs:
        audio_path = Path(f"media/audio/{song_file}")
        if not audio_path.exists():
            print(f"❌ 文件不存在: {audio_path}")
            continue

        print(f"\n{'='*70}")
        print(f"🎵 测试歌曲: {song_name}")
        print(f"{'='*70}")

        for threshold in thresholds:
            print(f"\n--- 阈值 {threshold} ---")
            segments = await test_threshold(audio_path, threshold)

            total = len(segments)
            first_start = segments[0]['start'] if segments else 0
            first_text = segments[0]['text'] if segments else ""

            print(f"片段数: {total}")
            print(f"第一句时间: {first_start:.1f}s")
            print(f"第一句内容: {first_text[:50]}")

            # 分析前3个片段的平均长度
            if len(segments) >= 3:
                avg_duration = sum(seg['end'] - seg['start'] for seg in segments[:3]) / 3
                print(f"前3个片段平均时长: {avg_duration:.1f}s")

            results.append({
                'song': song_name,
                'threshold': threshold,
                'segments': total,
                'first_start': first_start,
                'first_text': first_text[:30],
            })

    # 打印汇总表格
    print(f"\n\n{'='*70}")
    print("📊 汇总结果")
    print(f"{'='*70}")
    print(f"{'歌曲':<25} {'阈值':<8} {'片段数':<8} {'第一句时间':<12} 第一句内容")
    print("-" * 70)

    for r in results:
        print(f"{r['song']:<25} {r['threshold']:<8.2f} {r['segments']:<8} {r['first_start']:<12.1f} {r['first_text']}")

    # 分析建议
    print(f"\n\n{'='*70}")
    print("💡 分析建议")
    print(f"{'='*70}")

    # 按歌曲分组
    tom_results = [r for r in results if 'tom.mp3' in r['song'] or '江南' in r['song']]
    tunshi_results = [r for r in results if '吞噬星空' in r['song']]

    if tom_results:
        print("\n📌 tom.mp3（无前奏歌曲）:")
        print(f"   - 最多片段: 阈值 {min(tom_results, key=lambda x: -x['segments'])['threshold']} ({max(r['segments'] for r in tom_results)} 个)")
        print(f"   - 最少片段: 阈值 {max(tom_results, key=lambda x: -x['segments'])['threshold']} ({min(r['segments'] for r in tom_results)} 个)")

    if tunshi_results:
        print("\n📌 吞噬星空（12秒前奏）:")
        print(f"   - 最多片段: 阈值 {min(tunshi_results, key=lambda x: -x['segments'])['threshold']} ({max(r['segments'] for r in tunshi_results)} 个)")
        print(f"   - 最少片段: 阈值 {max(tunshi_results, key=lambda x: -x['segments'])['threshold']} ({min(r['segments'] for r in tunshi_results)} 个)")
        print(f"   - 第一句识别正确的阈值: {[r['threshold'] for r in tunshi_results if r['first_start'] > 10]}")

    print("\n🎯 推荐阈值:")
    print("   - 如果优先画面丰富度（更多片段）: 使用较低阈值 (0.6-0.7)")
    print("   - 如果优先前奏识别准确性: 使用较高阈值 (0.85-0.9)")
    print("   - 平衡选择: 0.75-0.8")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python
"""验证 TwelveLabs Marengo 配置是否正确。"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.infra.config.settings import get_settings
from src.services.matching.twelvelabs_client import TwelveLabsClient


def main() -> None:
    """显示当前 TwelveLabs 配置。"""
    settings = get_settings()
    client = TwelveLabsClient()

    print("=" * 60)
    print("TwelveLabs Marengo 配置验证")
    print("=" * 60)
    print()

    # 基础配置
    print("📋 基础配置:")
    print(f"  Index ID: {settings.tl_index_id}")
    print(f"  Live Enabled: {settings.tl_live_enabled}")
    print(f"  注意: 索引的引擎版本（Marengo 2.7/3.0 或 Pegasus）由创建索引时确定")
    print()

    # 搜索模态
    print("🔍 搜索模态配置:")
    print(f"  Visual (视觉): ✅ 始终启用")
    print(f"  Audio (音频): {'✅ 启用' if settings.tl_audio_search_enabled else '❌ 禁用'}")
    print(f"  Transcription (人声): {'✅ 启用' if settings.tl_transcription_search_enabled else '❌ 禁用'}")
    if settings.tl_transcription_search_enabled:
        print(f"    └─ 注意: 仅 Marengo 3.0 索引支持，2.7 索引会自动忽略")
    print()

    # 高级选项
    print("⚙️  高级搜索选项:")
    print(f"  Transcription Mode: {settings.tl_transcription_mode}")
    if settings.tl_transcription_mode == "lexical":
        print(f"    └─ 关键词精确匹配（适合产品名称、专业术语）")
    elif settings.tl_transcription_mode == "semantic":
        print(f"    └─ 语义匹配（理解含义，即使措辞不同）")
    else:
        print(f"    └─ 两者都用（返回最广泛结果）")

    print(f"  Search Operator: {settings.tl_search_operator}")
    print(f"    └─ {'匹配任意模态' if settings.tl_search_operator == 'or' else '同时匹配所有模态'}")

    print(f"  Confidence Threshold: {settings.tl_confidence_threshold}")
    print(f"    └─ {'不过滤低置信度结果' if settings.tl_confidence_threshold == 0 else f'过滤置信度 < {settings.tl_confidence_threshold} 的结果'}")
    print()

    # 实际搜索选项
    options_chain = client._build_option_chain()
    print("🎯 实际搜索选项:")
    print(f"  第一次尝试: {options_chain[0]}")
    if len(options_chain) > 1:
        print(f"  失败降级: {options_chain[1]}")

    if settings.tl_transcription_search_enabled:
        trans_opts = client._build_transcription_options()
        print(f"  Transcription Options: {trans_opts}")
    print()

    # 建议和警告
    print("💡 配置建议:")
    if not settings.tl_audio_search_enabled and not settings.tl_transcription_search_enabled:
        print("  ✅ 当前只使用 visual 模态，这是最安全的配置")
        print("  ✅ 适合搜索视觉场景、物体、动作、OCR 文字等")
        print("  ✅ 不会搜索音频或人声对话内容")
    else:
        print(f"  ⚠️  已启用额外模态，请确认您的索引支持:")
        if settings.tl_audio_search_enabled:
            print(f"     - audio: 会搜索音乐、环境声等音频")
            print(f"       → 需要索引的 model_options 包含 'audio'")
        if settings.tl_transcription_search_enabled:
            print(f"     - transcription: 会搜索人声对话内容")
            print(f"       → 需要索引是 Marengo 3.0 引擎且 model_options 包含 'transcription'")
        print()
        print("  ⚠️  重要提醒:")
        print("     如果您的索引不支持上述模态，搜索可能会失败！")
        print("     索引的 model_options 在创建时确定，创建后无法修改。")
        print("     请检查索引配置: https://api.twelvelabs.io/")

    print()
    print("=" * 60)
    print("验证完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""测试视频裁剪的边界检查功能。

测试场景：
1. 正常裁剪（范围在视频时长内）
2. 裁剪结束时间超出视频时长
3. 裁剪起始时间超出视频时长（应该使用循环模式）
"""

import sys
from pathlib import Path
import tempfile

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.services.matching.twelvelabs_video_fetcher import TwelveLabsVideoFetcher
from src.infra.config.settings import AppSettings
import structlog

logger = structlog.get_logger(__name__)


def test_boundary_checks():
    """测试边界检查功能。"""
    # 使用 fallback 视频测试（时长约 183 秒）
    test_video = Path("media/video/6911acda8bf751b791733149.mp4")

    if not test_video.exists():
        logger.error("test.video_not_found", path=test_video.as_posix())
        print(f"❌ 测试失败：找不到测试视频 {test_video}")
        return

    # 创建 TwelveLabsVideoFetcher 实例
    settings = AppSettings(
        tl_api_key="dummy",
        tl_index_id="dummy",
        postgres_dsn="dummy",
        redis_url="dummy",
        video_asset_dir="media/video",
    )
    fetcher = TwelveLabsVideoFetcher(settings)

    # 获取视频时长
    duration_ms = fetcher._get_video_duration_ms(test_video.as_posix())
    if not duration_ms:
        logger.error("test.duration_failed")
        print("❌ 无法获取视频时长")
        return

    logger.info("test.video_info", path=test_video.as_posix(), duration_ms=duration_ms, duration_s=duration_ms/1000)
    print(f"\n📹 测试视频信息：")
    print(f"   路径: {test_video}")
    print(f"   时长: {duration_ms}ms ({duration_ms/1000:.2f}秒)")

    test_cases = [
        {
            "name": "正常裁剪（范围内）",
            "start_ms": 10000,
            "end_ms": 12000,
            "expected": "success",
        },
        {
            "name": "结束时间略微超出",
            "start_ms": int(duration_ms) - 1000,
            "end_ms": int(duration_ms) + 1000,
            "expected": "adjusted",
        },
        {
            "name": "起始时间超出（循环模式）",
            "start_ms": int(duration_ms) + 5000,
            "end_ms": int(duration_ms) + 7000,
            "expected": "loop",
        },
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        print(f"\n🧪 开始测试边界检查功能...\n")

        for idx, case in enumerate(test_cases):
            target = tmp_path / f"clip_{idx}.mp4"

            logger.info(
                "test.case_start",
                name=case["name"],
                start_ms=case["start_ms"],
                end_ms=case["end_ms"],
            )
            print(f"{idx + 1}. {case['name']}")
            print(f"   裁剪范围: {case['start_ms']}ms - {case['end_ms']}ms")

            # 执行裁剪
            success = fetcher._cut_clip(
                test_video.as_posix(),
                case["start_ms"],
                case["end_ms"],
                target,
                "test_video",
                is_local=True,
            )

            if success and target.exists():
                # 验证输出时长
                output_duration_ms = fetcher._get_video_duration_ms(target.as_posix())
                expected_duration = case["end_ms"] - case["start_ms"]

                print(f"   ✅ 成功生成片段")
                print(f"   输出时长: {output_duration_ms}ms")
                print(f"   预期时长: {expected_duration}ms")

                logger.info(
                    "test.case_success",
                    name=case["name"],
                    output_duration_ms=output_duration_ms,
                    expected_duration_ms=expected_duration,
                )
            else:
                print(f"   ❌ 裁剪失败")
                logger.error("test.case_failed", name=case["name"])

            print()

    print("✅ 边界检查测试完成！")


if __name__ == "__main__":
    test_boundary_checks()

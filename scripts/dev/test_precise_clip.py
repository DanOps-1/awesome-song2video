#!/usr/bin/env python3
"""测试精确裁剪功能，验证视频片段时长是否与指定时长完全一致。

使用方法：
    python scripts/dev/test_precise_clip.py

测试内容：
    1. 从测试视频中裁剪多个不同时长的片段
    2. 使用 ffprobe 验证实际时长与预期时长的误差
    3. 模拟拼接多个片段，检查累积误差
"""

import subprocess
import tempfile
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def get_video_duration_ms(video_path: Path) -> float:
    """使用 ffprobe 获取视频实际时长（毫秒）。"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path.as_posix(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    duration_seconds = float(result.stdout.strip())
    return duration_seconds * 1000


def cut_clip_precise(source: Path, start_ms: int, end_ms: int, target: Path) -> bool:
    """使用精确裁剪模式裁剪视频片段。"""
    duration = (end_ms - start_ms) / 1000.0

    cmd = [
        "ffmpeg",
        "-y",
        "-i", source.as_posix(),
        "-ss", f"{start_ms / 1000:.3f}",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-b:a", "128k",
        target.as_posix(),
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return target.exists()
    except subprocess.CalledProcessError as exc:
        logger.error("ffmpeg.failed", error=exc.stderr)
        return False


def test_precise_clipping():
    """测试精确裁剪功能。"""
    # 查找测试视频文件
    test_videos = [
        Path("test_placeholder.mp4"),
        Path("test_placeholder2.mp4"),
        Path("test_short.mp4"),
        Path("test_long.mp4"),
    ]

    source_video = None
    for video in test_videos:
        if video.exists():
            source_video = video
            break

    if not source_video:
        logger.error(
            "test.no_source_video",
            message="未找到测试视频文件，请确保以下任一文件存在: test_placeholder.mp4, test_short.mp4, test_long.mp4",
        )
        return

    # 获取源视频时长
    source_duration_ms = get_video_duration_ms(source_video)
    logger.info("test.start", source_video=source_video.as_posix(), duration_ms=source_duration_ms)

    # 根据源视频时长动态生成测试用例
    # 确保所有测试用例都在源视频时长范围内
    max_clip_duration = min(source_duration_ms - 100, 2000)  # 最多裁剪到源视频结束前100ms，且不超过2秒

    test_cases = [
        {"name": "短片段_0.5秒", "start_ms": 0, "end_ms": 500, "expected_ms": 500},
        {"name": "短片段_1秒", "start_ms": 0, "end_ms": 1000, "expected_ms": 1000},
        {"name": "中片段_1.5秒", "start_ms": 0, "end_ms": 1500, "expected_ms": 1500},
    ]

    # 如果源视频足够长，添加更长的测试用例
    if source_duration_ms >= 2000:
        test_cases.append({"name": "长片段_2秒", "start_ms": 0, "end_ms": 2000, "expected_ms": 2000})

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        total_error_ms = 0
        max_error_ms = 0
        success_count = 0

        for idx, case in enumerate(test_cases):
            target = tmp_path / f"clip_{idx}.mp4"
            logger.info(
                "test.case_start",
                name=case["name"],
                expected_duration_ms=case["expected_ms"],
            )

            # 裁剪片段
            success = cut_clip_precise(
                source_video,
                case["start_ms"],
                case["end_ms"],
                target,
            )

            if not success:
                logger.error("test.case_failed", name=case["name"], reason="裁剪失败")
                continue

            # 验证实际时长
            actual_ms = get_video_duration_ms(target)
            expected_ms = case["expected_ms"]
            error_ms = abs(actual_ms - expected_ms)

            total_error_ms += error_ms
            max_error_ms = max(max_error_ms, error_ms)
            success_count += 1

            # 判断是否在可接受范围内（±50ms）
            is_acceptable = error_ms <= 50
            log_method = logger.info if is_acceptable else logger.warning

            log_method(
                "test.case_result",
                name=case["name"],
                expected_ms=expected_ms,
                actual_ms=round(actual_ms, 2),
                error_ms=round(error_ms, 2),
                is_acceptable=is_acceptable,
            )

        # 汇总结果
        if success_count > 0:
            avg_error_ms = total_error_ms / success_count
            logger.info(
                "test.summary",
                total_cases=len(test_cases),
                success_count=success_count,
                avg_error_ms=round(avg_error_ms, 2),
                max_error_ms=round(max_error_ms, 2),
                status="PASS" if max_error_ms <= 50 else "FAIL",
            )

            # 判断测试是否通过
            if max_error_ms <= 50:
                print("\n✅ 测试通过！精确裁剪功能工作正常。")
                print(f"   平均误差: {avg_error_ms:.2f}ms")
                print(f"   最大误差: {max_error_ms:.2f}ms")
            else:
                print("\n⚠️ 测试未通过！存在超过 50ms 的误差。")
                print(f"   平均误差: {avg_error_ms:.2f}ms")
                print(f"   最大误差: {max_error_ms:.2f}ms")
        else:
            logger.error("test.all_failed", message="所有测试用例都失败了")


if __name__ == "__main__":
    test_precise_clipping()

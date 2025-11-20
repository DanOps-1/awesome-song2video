#!/usr/bin/env python
"""测试日志功能。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.infra.observability.otel import configure_logging
import structlog

def main() -> None:
    # 配置日志
    configure_logging()

    # 获取 logger
    logger = structlog.get_logger(__name__)

    print("\n=== 测试日志输出 ===\n")

    # 测试不同级别的日志
    logger.info("test_info_log", message="这是一条信息日志", user="test_user", count=42)
    logger.warning("test_warning_log", message="这是一条警告日志", reason="测试")
    logger.error("test_error_log", message="这是一条错误日志", error_code=500)

    # 测试带异常的日志
    try:
        1 / 0
    except Exception as e:
        logger.exception("test_exception_log", message="捕获到异常")

    print("\n=== 日志测试完成 ===")
    print(f"日志文件位置: {ROOT / 'logs'}")
    print("- logs/app.log: 所有日志（JSON 格式）")
    print("- logs/error.log: 错误日志（JSON 格式）")

if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""验证日志配置是否在所有模块中生效。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("=" * 80)
print("验证日志配置")
print("=" * 80)

# 测试 1: API 模块
print("\n1. 测试 API 模块...")
from src.api.main import app  # noqa: F401
print("   ✅ API 模块已加载（日志配置应该已自动调用）")

# 测试 2: Worker 模块
print("\n2. 测试 Worker 模块...")
from src.workers import BaseWorkerSettings  # noqa: F401
print("   ✅ Worker 模块已加载（日志配置应该已自动调用）")

# 测试 3: 写入测试日志
print("\n3. 写入测试日志...")
import structlog
logger = structlog.get_logger(__name__)
logger.info("verify_logging_test", component="API", status="initialized")
logger.info("verify_logging_test", component="Worker", status="initialized")
print("   ✅ 测试日志已写入")

# 测试 4: 检查日志文件
print("\n4. 检查日志文件...")
log_dir = ROOT / "logs"
app_log = log_dir / "app.log"
error_log = log_dir / "error.log"

if app_log.exists():
    print(f"   ✅ app.log 存在 ({app_log.stat().st_size} bytes)")
else:
    print(f"   ❌ app.log 不存在")

if error_log.exists():
    print(f"   ✅ error.log 存在 ({error_log.stat().st_size} bytes)")
else:
    print(f"   ❌ error.log 不存在")

# 测试 5: 验证日志内容
print("\n5. 验证日志内容...")
if app_log.exists():
    import json
    with open(app_log) as f:
        lines = f.readlines()

    valid_count = 0
    for line in lines:
        try:
            data = json.loads(line)
            if "event" in data and "timestamp" in data:
                valid_count += 1
        except json.JSONDecodeError:
            pass

    print(f"   ✅ 找到 {valid_count} 条有效的 JSON 日志记录")
    print(f"   总行数: {len(lines)}")

    # 显示最后几条
    if valid_count > 0:
        print("\n   最后3条日志事件:")
        for line in lines[-3:]:
            try:
                data = json.loads(line)
                event = data.get("event", "N/A")
                level = data.get("level", "N/A")
                print(f"     - [{level}] {event}")
            except json.JSONDecodeError:
                print(f"     - (无法解析) {line.strip()}")

print("\n" + "=" * 80)
print("验证完成！")
print("=" * 80)
print(f"\n日志文件位置: {log_dir}")
print("- logs/app.log: 所有日志")
print("- logs/error.log: 错误日志")

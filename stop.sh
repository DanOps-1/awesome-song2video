#!/bin/bash
# 一键关闭项目

cd "$(dirname "$0")"

echo "=== 关闭 Song2Video 项目 ==="

# 关闭后端
echo "[1/3] 关闭后端..."
pkill -9 -f "uvicorn.*8000" 2>/dev/null && echo "✓ 后端已关闭" || echo "- 后端未运行"

# 关闭管理后台
echo "[2/3] 关闭管理后台..."
pkill -9 -f "vite.*6006" 2>/dev/null && echo "✓ 管理后台已关闭" || echo "- 管理后台未运行"

# 关闭用户前端
echo "[3/3] 关闭用户前端..."
pkill -9 -f "vite.*6008" 2>/dev/null && echo "✓ 用户前端已关闭" || echo "- 用户前端未运行"

# 清理esbuild进程
pkill -9 -f "esbuild" 2>/dev/null || true

# 等待进程完全退出
sleep 2

# 验证
echo ""
echo "=== 端口状态 ==="
if ss -tlnp | grep -q ":8000 "; then
    echo "警告: 端口 8000 仍被占用"
else
    echo "✓ 端口 8000 已释放"
fi

if ss -tlnp | grep -q ":6006 "; then
    echo "警告: 端口 6006 仍被占用"
else
    echo "✓ 端口 6006 已释放"
fi

if ss -tlnp | grep -q ":6008 "; then
    echo "警告: 端口 6008 仍被占用"
else
    echo "✓ 端口 6008 已释放"
fi

echo ""
echo "=== 关闭完成 ==="

#!/bin/bash
# 一键关闭项目

cd "$(dirname "$0")"

echo "=== 关闭 Song2Video 项目 ==="

# [1/5] 关闭后端
echo "[1/5] 关闭后端..."
pkill -9 -f "uvicorn.*8000" 2>/dev/null && echo "✓ 后端已关闭" || echo "- 后端未运行"

# [2/5] 关闭 Timeline Worker
echo "[2/5] 关闭 Timeline Worker..."
pkill -9 -f "src.workers.timeline_worker" 2>/dev/null && echo "✓ Timeline Worker 已关闭" || echo "- Timeline Worker 未运行"

# [3/5] 关闭 Render Worker
echo "[3/5] 关闭 Render Worker..."
pkill -9 -f "src.workers.render_worker" 2>/dev/null && echo "✓ Render Worker 已关闭" || echo "- Render Worker 未运行"

# [4/5] 关闭管理后台
echo "[4/5] 关闭管理后台..."
pkill -9 -f "vite.*6006" 2>/dev/null && echo "✓ 管理后台已关闭" || echo "- 管理后台未运行"

# [5/5] 关闭用户前端
echo "[5/5] 关闭用户前端..."
pkill -9 -f "vite.*6008" 2>/dev/null && echo "✓ 用户前端已关闭" || echo "- 用户前端未运行"

# 清理 esbuild 进程
pkill -9 -f "esbuild" 2>/dev/null || true

# 等待进程完全退出
sleep 2

# 验证
echo ""
echo "=== 服务状态 ==="

# 检查 Redis（不关闭，仅显示状态）
if redis-cli ping > /dev/null 2>&1; then
    echo "ℹ Redis (6379) 仍在运行（作为共享服务保留）"
else
    echo "- Redis (6379) 未运行"
fi

# 检查端口
if ss -tlnp | grep -q ":8000 "; then
    echo "警告: 端口 8000 仍被占用"
else
    echo "✓ 端口 8000 已释放"
fi

# 检查 Workers
if pgrep -f "src.workers.timeline_worker" > /dev/null; then
    echo "警告: Timeline Worker 仍在运行"
else
    echo "✓ Timeline Worker 已停止"
fi

if pgrep -f "src.workers.render_worker" > /dev/null; then
    echo "警告: Render Worker 仍在运行"
else
    echo "✓ Render Worker 已停止"
fi

# 检查前端端口
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
echo ""
echo "提示: Redis 作为共享服务未被关闭。如需关闭 Redis，请运行:"
echo "  redis-cli shutdown"

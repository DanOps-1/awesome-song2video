#!/bin/bash
# 一键关闭项目 - 强力版

cd "$(dirname "$0")"

echo "=== 关闭 Song2Video 项目 ==="

# 强力杀死进程的函数
force_kill() {
    local pattern="$1"
    local name="$2"

    # 方法1: pkill
    pkill -9 -f "$pattern" 2>/dev/null

    # 方法2: 通过 ps + kill 确保杀干净
    local pids=$(ps aux | grep -E "$pattern" | grep -v grep | awk '{print $2}')
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null
    fi

    sleep 1

    # 验证
    if pgrep -f "$pattern" > /dev/null 2>&1; then
        echo "警告: $name 仍有进程残留，强制清理..."
        pkill -9 -f "$pattern" 2>/dev/null
        sleep 1
    fi
}

# [1/5] 关闭后端 (所有 uvicorn 相关进程)
echo "[1/5] 关闭后端..."
force_kill "uvicorn.*src.api.main" "后端"
force_kill "uvicorn.*8000" "后端"
# 清理可能的子进程
pkill -9 -f "python.*src.api" 2>/dev/null || true

# [2/5] 关闭 Timeline Worker
echo "[2/5] 关闭 Timeline Worker..."
force_kill "timeline_worker" "Timeline Worker"
force_kill "arq.*timeline" "Timeline Worker"

# [3/5] 关闭 Render Worker
echo "[3/5] 关闭 Render Worker..."
force_kill "render_worker" "Render Worker"
force_kill "arq.*render" "Render Worker"

# [4/5] 关闭管理后台
echo "[4/5] 关闭管理后台..."
force_kill "vite.*6006" "管理后台"
force_kill "node.*web" "管理后台"

# [5/5] 关闭用户前端
echo "[5/5] 关闭用户前端..."
force_kill "vite.*6008" "用户前端"
force_kill "node.*frontend" "用户前端"

# 清理所有 esbuild 和 node 相关进程
pkill -9 -f "esbuild" 2>/dev/null || true

# 等待进程完全退出
sleep 2

# 清理 Python 缓存（确保下次启动使用最新代码）
echo ""
echo "清理 Python 缓存..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

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
check_port() {
    if ss -tlnp 2>/dev/null | grep -q ":$1 "; then
        echo "警告: 端口 $1 仍被占用"
        # 显示占用进程
        ss -tlnp 2>/dev/null | grep ":$1 " | head -1
        return 1
    else
        echo "✓ 端口 $1 已释放"
        return 0
    fi
}

check_port 8000
check_port 6006
check_port 6008

# 检查 Workers
if pgrep -f "timeline_worker" > /dev/null 2>&1; then
    echo "警告: Timeline Worker 仍在运行"
    pgrep -af "timeline_worker"
else
    echo "✓ Timeline Worker 已停止"
fi

if pgrep -f "render_worker" > /dev/null 2>&1; then
    echo "警告: Render Worker 仍在运行"
    pgrep -af "render_worker"
else
    echo "✓ Render Worker 已停止"
fi

echo ""
echo "=== 关闭完成 ==="
echo ""
echo "提示: "
echo "  - Redis 作为共享服务未被关闭。如需关闭: redis-cli shutdown"
echo "  - Python 缓存已清理，下次启动将使用最新代码"

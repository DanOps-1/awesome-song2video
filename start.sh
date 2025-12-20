#!/bin/bash
# 一键启动项目 - 确保加载最新代码

set -e
cd "$(dirname "$0")"

echo "=== 启动 Song2Video 项目 ==="

# [预处理] 调用 stop.sh 彻底清理旧进程
echo ""
echo "=== 预处理：清理旧进程 ==="
if [ -f "./stop.sh" ]; then
    bash ./stop.sh 2>/dev/null || true
else
    echo "警告: stop.sh 不存在，尝试手动清理..."
    pkill -9 -f "uvicorn.*src.api" 2>/dev/null || true
    pkill -9 -f "arq.*worker" 2>/dev/null || true
    pkill -9 -f "vite.*600" 2>/dev/null || true
fi

# 清理 Python 缓存（确保加载最新代码）
echo ""
echo "清理 Python 缓存..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# 确保日志目录存在
mkdir -p logs

# 检查端口是否被占用
check_port() {
    if ss -tlnp 2>/dev/null | grep -q ":$1 "; then
        echo "警告: 端口 $1 已被占用，尝试清理..."
        return 1
    fi
    return 0
}

# [0/5] 检查并启动 Redis
echo "[0/5] 检查 Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis 已运行"
else
    echo "Redis 未运行，正在启动..."
    redis-server --daemonize yes --port 6379
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo "✓ Redis 启动成功"
    else
        echo "✗ Redis 启动失败，请手动检查"
        exit 1
    fi
fi

# [1/5] 启动后端
echo ""
echo "[1/5] 启动后端 (端口 8000)..."
nohup uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "后端 PID: $BACKEND_PID"

# 等待后端启动（reload 模式启动较慢，需要加载模型，约需 45 秒）
echo "等待后端启动（首次启动较慢，请耐心等待）..."
for i in {1..60}; do
    if ss -tlnp 2>/dev/null | grep -q ":8000 "; then
        echo "✓ 后端启动成功 (${i}秒)"
        break
    fi
    sleep 1
    if [ $i -eq 60 ]; then
        echo "✗ 后端启动超时，请检查 logs/backend.log"
        exit 1
    fi
done

# [2/5] 启动 Timeline Worker（歌词识别、视频匹配）
echo "[2/5] 启动 Timeline Worker..."
nohup uv run arq src.workers.timeline_worker.WorkerSettings > logs/timeline_worker.log 2>&1 &
TIMELINE_PID=$!
echo "Timeline Worker PID: $TIMELINE_PID"

# [3/5] 启动 Render Worker（视频渲染）
echo "[3/5] 启动 Render Worker..."
nohup uv run arq src.workers.render_worker.WorkerSettings > logs/render_worker.log 2>&1 &
RENDER_PID=$!
echo "Render Worker PID: $RENDER_PID"

# [4/5] 启动管理后台
echo "[4/5] 启动管理后台 (端口 6006)..."
cd apps/web
nohup npm run dev -- --port 6006 --host 0.0.0.0 > ../../logs/admin.log 2>&1 &
ADMIN_PID=$!
echo "管理后台 PID: $ADMIN_PID"
cd ../..

# [5/5] 启动用户前端
echo "[5/5] 启动用户前端 (端口 6008)..."
cd apps/frontend
nohup npm run dev -- --port 6008 --host 0.0.0.0 > ../../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "用户前端 PID: $FRONTEND_PID"
cd ../..

# 等待前端启动（Vite 启动较慢，约需 15 秒）
echo ""
echo "等待前端服务启动..."
sleep 15
echo ""
echo "=== 服务状态 ==="

# 检查 Redis
if redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis (6379) 运行中"
else
    echo "✗ Redis (6379) 未运行"
fi

# 检查后端
if ss -tlnp | grep -q ":8000 "; then
    echo "✓ 后端 (8000) 运行中"
else
    echo "✗ 后端 (8000) 启动失败"
fi

# 检查 Workers
if pgrep -f "arq src.workers.timeline_worker" > /dev/null; then
    echo "✓ Timeline Worker 运行中"
else
    echo "✗ Timeline Worker 未运行"
fi

if pgrep -f "arq src.workers.render_worker" > /dev/null; then
    echo "✓ Render Worker 运行中"
else
    echo "✗ Render Worker 未运行"
fi

# 检查前端
if ss -tlnp | grep -q ":6006 "; then
    echo "✓ 管理后台 (6006) 运行中"
else
    echo "✗ 管理后台 (6006) 启动失败"
fi

if ss -tlnp | grep -q ":6008 "; then
    echo "✓ 用户前端 (6008) 运行中"
else
    echo "✗ 用户前端 (6008) 启动失败"
fi

echo ""
echo "=== 启动完成 ==="
echo "后端API:   http://localhost:8000"
echo "管理后台:  http://localhost:6006"
echo "用户前端:  http://localhost:6008"
echo "API文档:   http://localhost:8000/docs"
echo ""
echo "查看日志:"
echo "  后端:           tail -f logs/backend.log"
echo "  Timeline Worker: tail -f logs/timeline_worker.log"
echo "  Render Worker:   tail -f logs/render_worker.log"
echo "  管理后台:       tail -f logs/admin.log"
echo "  用户前端:       tail -f logs/frontend.log"

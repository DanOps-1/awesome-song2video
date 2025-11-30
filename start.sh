#!/bin/bash
# 一键启动项目

set -e
cd "$(dirname "$0")"

echo "=== 启动 Song2Video 项目 ==="

# 检查端口是否被占用
check_port() {
    if ss -tlnp | grep -q ":$1 "; then
        echo "警告: 端口 $1 已被占用，尝试清理..."
        return 1
    fi
    return 0
}

# 启动后端
echo "[1/3] 启动后端 (端口 8000)..."
if ! check_port 8000; then
    pkill -9 -f "uvicorn.*8000" 2>/dev/null || true
    sleep 2
fi
nohup uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "后端 PID: $BACKEND_PID"

# 等待后端启动
sleep 5
if ss -tlnp | grep -q ":8000 "; then
    echo "✓ 后端启动成功"
else
    echo "✗ 后端启动失败，请检查 logs/backend.log"
    exit 1
fi

# 启动管理后台
echo "[2/3] 启动管理后台 (端口 6006)..."
if ! check_port 6006; then
    pkill -9 -f "vite.*6006" 2>/dev/null || true
    sleep 2
fi
cd web
nohup npm run dev -- --port 6006 --host 0.0.0.0 > ../logs/admin.log 2>&1 &
ADMIN_PID=$!
echo "管理后台 PID: $ADMIN_PID"
cd ..

# 启动用户前端
echo "[3/3] 启动用户前端 (端口 6008)..."
if ! check_port 6008; then
    pkill -9 -f "vite.*6008" 2>/dev/null || true
    sleep 2
fi
cd frontend
nohup npm run dev -- --port 6008 --host 0.0.0.0 > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "用户前端 PID: $FRONTEND_PID"
cd ..

# 等待前端启动
sleep 10
echo ""
echo "=== 服务状态 ==="
if ss -tlnp | grep -q ":8000 "; then
    echo "✓ 后端 (8000) 运行中"
else
    echo "✗ 后端 (8000) 启动失败"
fi

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
echo "  后端:     tail -f logs/backend.log"
echo "  管理后台: tail -f logs/admin.log"
echo "  用户前端: tail -f logs/frontend.log"

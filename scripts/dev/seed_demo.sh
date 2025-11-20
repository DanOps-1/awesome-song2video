#!/usr/bin/env bash
# =============================================================================
# Demo 数据种子脚本
# =============================================================================
# 功能：
# 1. 检查 fallback 视频是否存在
# 2. 创建 demo mix 并触发 timeline 生成
# 3. 调用 preview/render API 验证流程

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MEDIA_ROOT="${MEDIA_ROOT:-$REPO_ROOT/media}"
API_BASE="${API_BASE:-http://localhost:8080}"
MIX_REQUEST_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mix-request)
      MIX_REQUEST_FILE="$2"
      shift 2
      ;;
    *)
      echo -e "${RED:-}未知参数: $1${NC:-}"
      exit 1
      ;;
  esac
done

# 加载环境变量
if [ -f "$REPO_ROOT/.env" ]; then
  source "$REPO_ROOT/.env"
else
  echo "错误: .env 文件不存在，请先从 .env.example 复制并配置"
  exit 1
fi

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}歌词混剪 Demo 种子脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# -----------------------------------------------------------------------------
# 1. 检查 fallback 视频
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/4] 检查 fallback 视频...${NC}"

FALLBACK_VIDEO_ID="${FALLBACK_VIDEO_ID:-6911acda8bf751b791733149}"
FALLBACK_VIDEO_PATH="$MEDIA_ROOT/video/$FALLBACK_VIDEO_ID.mp4"

if [ ! -f "$FALLBACK_VIDEO_PATH" ]; then
  echo -e "${RED}警告: fallback 视频不存在: $FALLBACK_VIDEO_PATH${NC}"
  echo "请下载 demo 视频到该路径，或更新 FALLBACK_VIDEO_ID 环境变量"
  exit 1
fi

echo -e "${GREEN}✓ fallback 视频存在: $FALLBACK_VIDEO_PATH${NC}"

# -----------------------------------------------------------------------------
# 2. 创建 demo mix（需要 API 已启动）
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/4] 创建 demo mix...${NC}"

# 检查 API 是否可用
if ! curl -s "$API_BASE/health" > /dev/null 2>&1; then
  echo -e "${RED}错误: API 服务未启动 ($API_BASE)${NC}"
  echo "请先运行: uvicorn src.api.main:app --reload --port 8080"
  exit 1
fi

# 构建 mix payload（默认歌词 or 自定义文件）
if [[ -n "$MIX_REQUEST_FILE" ]]; then
  if [[ "$MIX_REQUEST_FILE" != /* ]]; then
    CANDIDATE="$REPO_ROOT/scripts/dev/mix_requests/$MIX_REQUEST_FILE"
  else
    CANDIDATE="$MIX_REQUEST_FILE"
  fi

  if [[ ! -f "$CANDIDATE" ]]; then
    echo -e "${RED}错误: 指定的 mix-request 文件不存在: $CANDIDATE${NC}"
    exit 1
  fi
  MIX_PAYLOAD="$(cat "$CANDIDATE")"
else
  MIX_PAYLOAD="$(cat <<'JSON'
{
  "song_title": "Demo Mix - 并行裁剪演示",
  "artist": "Demo Artist",
  "source_type": "upload",
  "lyrics_text": "I gotta believe\nI can more than survive\nStill one trick up my sleeve\nWe're gonna make this one shot\nI'm at the edge of my life\nI've got no time to think twice",
  "language": "en",
  "auto_generate": true
}
JSON
)"
fi

# 创建 mix（POST /api/v1/mixes）
MIX_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/mixes" \
  -H "Content-Type: application/json" \
  -d "$MIX_PAYLOAD" || echo '{"error": "API call failed"}')

MIX_ID=$(echo "$MIX_RESPONSE" | grep -o '"id":"[^"]*' | cut -d'"' -f4 | head -1)

if [ -z "$MIX_ID" ]; then
  echo -e "${RED}错误: 创建 mix 失败${NC}"
  echo "响应: $MIX_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✓ 已创建 mix: $MIX_ID${NC}"

# -----------------------------------------------------------------------------
# 3. 调用 preview API 验证 manifest
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/4] 等待 timeline 生成并调用 preview API...${NC}"

# 等待 timeline worker 完成（最多 60 秒）
for i in {1..12}; do
  PREVIEW_RESPONSE=$(curl -s "$API_BASE/api/v1/mixes/$MIX_ID/preview" || echo '{"error": "not ready"}')

  if echo "$PREVIEW_RESPONSE" | grep -q '"manifest"'; then
    echo -e "${GREEN}✓ Preview manifest 已生成${NC}"

    # 显示关键指标
    LINE_COUNT=$(echo "$PREVIEW_RESPONSE" | grep -o '"line_count":[0-9]*' | cut -d':' -f2)
    FALLBACK_COUNT=$(echo "$PREVIEW_RESPONSE" | grep -o '"fallback_count":[0-9]*' | cut -d':' -f2)
    AVG_DELTA=$(echo "$PREVIEW_RESPONSE" | grep -o '"avg_delta_ms":[0-9.]*' | cut -d':' -f2)

    echo "  - 歌词行数: $LINE_COUNT"
    echo "  - Fallback 行数: $FALLBACK_COUNT"
    echo "  - 平均对齐偏差: ${AVG_DELTA}ms"
    break
  fi

  echo "  等待 timeline 生成... ($i/12)"
  sleep 5
done

if ! echo "$PREVIEW_RESPONSE" | grep -q '"manifest"'; then
  echo -e "${RED}错误: timeline 生成超时或失败${NC}"
  exit 1
fi

# -----------------------------------------------------------------------------
# 4. 提交渲染任务
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/4] 提交渲染任务...${NC}"

RENDER_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/mixes/$MIX_ID/render" \
  -H "Content-Type: application/json" \
  -d '{}' || echo '{"error": "render failed"}')

JOB_ID=$(echo "$RENDER_RESPONSE" | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$JOB_ID" ]; then
  echo -e "${RED}警告: 渲染任务提交失败${NC}"
  echo "响应: $RENDER_RESPONSE"
else
  echo -e "${GREEN}✓ 渲染任务已提交: $JOB_ID${NC}"
  echo "查询状态: curl \"$API_BASE/api/v1/mixes/$MIX_ID/render?job_id=$JOB_ID\""
fi

# -----------------------------------------------------------------------------
# 完成
# -----------------------------------------------------------------------------
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Demo 种子脚本执行完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "后续步骤："
echo "1. 查看 preview manifest: curl \"$API_BASE/api/v1/mixes/$MIX_ID/preview\" | jq"
echo "2. 监控渲染进度: watch -n 2 \"curl -s '$API_BASE/api/v1/mixes/$MIX_ID/render?job_id=$JOB_ID' | jq\""
echo "3. 查看 Prometheus 指标: http://localhost:9090/graph?g0.expr=lyrics_preview_avg_delta_ms"
echo "4. 查看 Loki 日志: http://localhost:3000 (Grafana)"

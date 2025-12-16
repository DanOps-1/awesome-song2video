# Quickstart：歌词语义混剪视频

## 环境准备

1. 安装 Python 3.11，并执行 `pip install -r requirements.txt`（包含 FastAPI、httpx、twelvelabs、sqlmodel、redis-asyncio、arq、pydub、python-ffmpeg`）。
2. 启动基础服务：
   - PostgreSQL 15（创建数据库 `lyrics_mix`）。
   - Redis 7（开启持久化）。
   - MinIO（设置 `MEDIA_BUCKET`）。
3. 配置环境变量（均使用中文注释）：
   - `TL_API_KEY`：从密钥管理服务注入。
   - `TL_INDEX_ID=6911aaadd68fb776bc1bd8e7`。
   - `POSTGRES_DSN`、`REDIS_URL`、`MINIO_ENDPOINT`。
4. 运行数据库迁移 `alembic upgrade head`。

## 启动服务

```bash
# API 服务（热重载）
uvicorn src.api.main:app --reload --port 8080

# 时间线/匹配 worker
arq src.workers.timeline_worker.WorkerSettings

# 渲染 worker（FFmpeg 节点）
arq src.workers.render_worker.WorkerSettings
```

## 基本流程

1. `POST /api/v1/mixes` 上传歌曲与歌词（或引用歌曲库）。
2. `POST /api/v1/mixes/{mix_id}/generate-timeline` 触发自动匹配，等待状态变为 `generated`。
3. 前端调用 `GET /api/v1/mixes/{mix_id}/lines` 展示时间线，人工可通过 `PATCH /lines/{line_id}` 或 `POST /search` 校正片段。
4. 时间线全部 `locked` 后，`POST /api/v1/mixes/{mix_id}/render` 提交渲染，轮询 `GET .../render` 直至 `success`，随后下载返回的对象存储 URL。

## 测试与质量

- 运行 `pytest`：包含 `pytest-asyncio` 单元、`tests/contract` API 契约、`tests/golden` 渲染黄金用例。
- 执行 `ruff check` + `mypy` 保证静态质量。
- 使用 `scripts/dev/seed_demo.sh` 创建示例歌曲与媒资，便于联调。

## 故障排查

- TwelveLabs 调用失败：检查 `match` worker 日志中的 trace_id，确认配额与索引状态。
- 渲染耗时过长：查看 `RenderJob` 的 `ffmpeg_script`，确认是否落在 GPU 节点；必要时调高 worker 并发。
- 时间线缺少片段：使用备用 B-roll 资产库 API `/api/v1/assets/broll` 进行填充。

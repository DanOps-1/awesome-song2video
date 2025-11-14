# Quickstart：检查 manifest、指标与 fallback

## 1. 准备环境
1. 创建虚拟环境并安装依赖：`poetry install` 或 `pip install -r requirements.txt`。
2. 启动 PostgreSQL/Redis，本地可使用 `docker compose up db redis`，确保端口与 `.env` 一致。
3. 下载 demo 媒资到 `media/audio/tom.mp3`、`media/video/6911acda8bf751b791733149.mp4`，并在 `.env` 中设置：
   ```env
   TL_INDEX_ID=6911aaadd68fb776bc1bd8e7
   FALLBACK_VIDEO_ID=6911acda8bf751b791733149
   ENABLE_ASYNC_QUEUE=false
   ```

## 2. 运行核心服务
1. 启动 API：`uvicorn src.api.main:app --reload --port 8080`。
2. 执行时间线 worker：`arq src.workers.timeline_worker.WorkerSettings`。
3. 执行渲染 worker：`arq src.workers.render_worker.WorkerSettings`（或 `python -m src.workers.render_worker` 调试）。

## 3. 写入 demo 混剪任务
1. 运行 `scripts/dev/seed_demo.sh` 创建 mix，并触发歌词 ingest/TwelveLabs 匹配。
2. 观察日志 `timeline_builder.candidates`，确认每句歌词返回 3 个候选或 fallback warning。

## 4. 验证 Preview Manifest
1. 调用 `GET http://localhost:8080/api/v1/mixes/{mix_id}/preview`。
2. 断言响应包含：
   - `manifest[*].fallback` 与 `fallback_reason`。
   - `metrics.preview.line_count == 歌词行数`。
   - `metrics.preview.fallback_count` 统计缺失候选。
3. 若返回 404，检查 `song_mix_requests.metrics` 是否为空并重新运行时间线生成。

## 5. 验证渲染指标
1. 提交渲染：`POST /api/v1/mixes/{mix_id}/render`。
2. 等待日志中出现 `render_worker.storage_todo`，记录本地产物路径。
3. 调用 `GET /api/v1/mixes/{mix_id}/render?job_id=...`，确认 `metrics.render` 中 `avg_delta_ms/max_delta_ms/total_duration_ms` 均 > 0。
4. 使用 `ffprobe` 检查输出视频与字幕文件，确保画面对齐。

## 6. 观测与报警
1. 在 Prometheus 查询 `lyrics_preview_avg_delta_ms`、`render_alignment_max_delta_ms`，验证 5 分钟内刷新。
2. 在 Loki 中搜索 `render_worker.storage_todo`，确认对象存储 TODO 被记录。
3. 若 MinIO 上线，替换日志为真正上传逻辑并更新 runbook。

## 7. 测试与质量
1. 运行 `pytest tests/unit/services/test_preview_service.py` 与渲染 worker 单测，覆盖指标计算与 fallback。
2. 运行 `pytest tests/contract/api/test_preview_render.py`，确保 API schema 与 YAML 契约一致。
3. 执行 `ruff check` 与 `mypy --strict`，保证类型/风格符合宪章。

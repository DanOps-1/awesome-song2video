# Quickstart — 渲染 Worker 并行异步裁剪

## 1. 准备环境
1. 复制 `.env.example` 为 `.env`，新增/确认：
   ```env
   TL_LIVE_ENABLED=true
   RENDER_CLIP_CONCURRENCY=4
   RENDER_CONFIG_CHANNEL=render:config
   PLACEHOLDER_CLIP_PATH=media/fallback/clip_placeholder.mp4
   ```
   - `RENDER_CLIP_CONCURRENCY`：控制 clip 级并行槽位，默认 4，可视节点性能调整。
   - `RENDER_CONFIG_CHANNEL`：Redis Pub/Sub 频道名，patch API 更新后即刻推送。
   - `PLACEHOLDER_CLIP_PATH`：指向 3 秒黑屏占位素材的绝对或相对路径。
2. 运行 Redis、PostgreSQL、MinIO（如需）并确保 `scripts/dev/seed_demo.sh` 可创建示例歌曲。
3. 在 `media/fallback/` 目录放置 3 秒黑屏占位片段（H.264 + AAC，命名 `clip_placeholder.mp4`）。

## 2. 启动服务
1. `uvicorn src.api.main:app --reload --port 8080`（供 API/运营端触发混剪）。
2. `arq src.workers.timeline_worker.WorkerSettings`（构建歌词时间线）。
3. `arq src.workers.render_worker.WorkerSettings`（执行并行裁剪）。
4. 可选：`docker compose up otel`（若需查看 Prometheus/Loki 指标）。

## 3. 提交测试任务
1. 执行 `scripts/dev/seed_demo.sh --mix-request slow_render_case.json`，生成含 60 行歌词的请求。
2. 通过 API 或直接调用 `SongMixRepository.lock_lines` 把歌词锁定；确认 `SongMixRequest.timeline_status == "generated"`。
3. 在数据库或 API 中创建渲染 Job，观察 render worker 日志：
   - `twelvelabs.video_clip` 会显示 `clip_task_id`、`parallel_slot`。
   - `render_clip_inflight` Prometheus Gauge 会出现 4 条并发。
4. 若需热更新并发：
   ```bash
   redis-cli publish render:config '{"max_parallelism":6,"max_retry":3}'
   ```
   渲染 Worker 将日志 `render_worker.config_hot_reload`。

## 4. 验证输出
1. 生成的 MP4/SRT 位于 `artifacts/renders/<job_id>.mp4|srt`。
2. 检查数据库 `render_jobs.metrics -> render.clip_stats`，确认 `peak_parallelism`、`placeholder_tasks` 等字段存在。
3. 运行 `pytest tests/unit/workers/test_render_worker_parallel.py tests/integration/test_render_pipeline.py` 确认新逻辑通过。
4. Prometheus 需能抓取以下指标：
   - `render_clip_inflight{worker="render"}`：并发槽位。
   - `render_clip_failures_total{reason="twelvelabs_http"}`：失败分类。
   - `render_clip_placeholder_total`：占位片段使用次数。
   Grafana 面板示例位于 `docs/observability/render_dashboard.md`。

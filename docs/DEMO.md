# 功能演示：并行裁剪 + 占位回退

本文档用于现场演示 `001-async-render` 的全部交付：clip 级并行裁剪、渲染配置热加载、占位片段回退与可观测指标。所有命令均在项目根目录执行，并假设 `.venv` 已安装 `.[dev]` 依赖。

## 0. 场景准备

```bash
cp .env.example .env
python scripts/media/create_placeholder_clip.py  # 生成 3 秒黑屏占位素材
scripts/dev/seed_demo.sh --mix-request slow_render_case.json

# 启动 API 与 Worker
uvicorn src.api.main:app --port 8080 --reload &
arq src.workers.timeline_worker.WorkerSettings &
arq src.workers.render_worker.WorkerSettings &
```

- Demo 所有日志皆为结构化 JSON，必须包含 `trace_id`。
- Redis 默认监听 `render:config` 频道，用于热加载 `RenderClipConfig`。
- 占位素材默认写入 `media/fallback/clip_placeholder.mp4`。

---

## Demo 1：并行裁剪吞吐验证

**目标**：使用 60 行歌词的慢速样本验证 TaskGroup 并发裁剪、clip_stats 写入与指标暴露。

### 步骤
1. 触发渲染：`pytest tests/integration/render/test_parallel_clip_pipeline.py -k slow_case`
2. 观察 worker 日志（示例）：
   ```text
   2025-11-19 15:24:05 [info] twelvelabs.video_clip
     trace_id=abcd...
     clip_task_id=task_y7d5
     parallel_slot=2
     video_id=691aef4a2fc9d91d9c80dd86
   2025-11-19 15:24:05 [info] render_worker.clip_stats
     trace_id=abcd...
     peak_parallelism=4
     avg_clip_duration_ms=2300
     placeholder_tasks=0
   ```
3. Prometheus 验证：
   - `render_clip_inflight{worker="render"}` 峰值= `RENDER_CLIP_CONCURRENCY`。
   - `render_clip_duration_ms_bucket` 呈现裁剪时长直方图。
4. 数据库验证：
   ```sql
   SELECT
     id,
     json_extract(metrics, '$.render.clip_stats.peak_parallelism') AS peak_parallelism,
     json_extract(metrics, '$.render.clip_stats.placeholder_tasks') AS placeholder_tasks,
     json_extract(metrics, '$.render.clip_stats.total_clips') AS total_clips
   FROM render_jobs
   ORDER BY submitted_at DESC
   LIMIT 1;
   ```

### 通过标准
- `peak_parallelism` ≥ 4，且 `total_clips` == 60。
- Loki 中存在 `twelvelabs.video_clip`、`render_worker.clip_task_completed` 结构化日志。
- `render_clip_failures_total`、`render_clip_placeholder_total` 与预期失败次数一致。

---

## Demo 2：渲染配置 API + 热加载

**目标**：通过 `/api/v1/render/config` 动态调整并发与重试次数，验证 Redis Pub/Sub 热加载。

### 步骤
1. 读取当前配置：
   ```bash
   curl -s http://localhost:8080/api/v1/render/config | jq
   ```
2. 提交变更（示例：并行=6，占位路径为自定义文件）：
   ```bash
   curl -X PATCH http://localhost:8080/api/v1/render/config \
     -H "Content-Type: application/json" \
     -d '{"max_parallelism":6,"per_video_limit":2,"max_retry":3,"placeholder_asset_path":"media/fallback/clip_placeholder.mp4"}'
   ```
3. Worker 日志应即时输出：
   ```text
   2025-11-19 15:25:10 [info] render_worker.config_hot_reload
     trace_id=efgh...
     new_parallelism=6
     per_video_limit=2
     max_retry=3
   ```
4. `redis-cli monitor` 可看到 `publish render:config ...` 记录；指标 `render_config_update_total`（如已接入）递增。

### 通过标准
- PATCH 之后再次 GET 返回新参数。
- Worker 无需重启即可打印 `config_version` 更新日志。
- 并行峰值随配置更新（可再次运行 Demo 1 验证）。

---

## Demo 3：占位片段回退链路

**目标**：模拟 CDN/HLS 多次失败，确认占位片段写入、回退指标与日志。

### 步骤
1. 运行集成测试：`pytest tests/integration/render/test_render_fallbacks.py`
2. 关注日志：
   ```text
   2025-11-19 15:24:02 [warning] twelvelabs.retrieve_exception
     trace_id=ijkl...
     video_id=6911acda8bf751b791733149
     error="[Errno 8] nodename nor servname provided"
   2025-11-19 15:24:02 [info] render_worker.placeholder_inserted
     trace_id=ijkl...
     clip_task_id=task_p3x4
     fallback_reason="cdns_unreachable"
   ```
3. DB 验证：
   ```sql
   SELECT
     json_extract(metrics, '$.render.clip_stats.placeholder_tasks') AS placeholder_tasks,
     json_extract(metrics, '$.render.clip_stats.failed_tasks') AS failed_tasks,
     json_extract(metrics, '$.render.clip_stats.fallback_reason_counts') AS fallback_reason_counts
   FROM render_jobs
   ORDER BY submitted_at DESC
   LIMIT 1;
   ```
4. Prometheus：
   - `render_clip_placeholder_total` == `placeholder_tasks`
   - `render_clip_failures_total` 统计失败次数

5. 生成的占位 MP4 位于 `artifacts/render_tmp/job_<id>/clip_<n>.mp4`，并在清理阶段自动删除。

### 通过标准
- `placeholder_tasks` > 0 且 `fallback_reason_counts` 包含 `cdn_error` / `no_candidates`。
- Loki 中搜索 `fallback_reason` 关键字可找到对应日志。
- 回退后 tetap 生成整段渲染结果，clip_stats 中 `total_clips` == 请求行数。

---

## Demo 附录：命令速查

| 目的 | 命令 |
| --- | --- |
| 并行渲染回归 | `pytest tests/integration/render/test_parallel_clip_pipeline.py` |
| 占位回退回归 | `pytest tests/integration/render/test_render_fallbacks.py` |
| 渲染配置契约 | `pytest tests/contract/api/test_render_config.py` |
| 生成占位素材 | `python scripts/media/create_placeholder_clip.py` |
| 触发热加载 | `redis-cli publish render:config '{"max_parallelism":6,...}'` |

> **提示**：所有指标面板位于 `docs/observability/render_dashboard.md`，包含 `render_clip_inflight`、`render_clip_placeholder_total`、`render_clip_failures_total`、`render_clip_duration_ms` 的 Grafana 图表说明。

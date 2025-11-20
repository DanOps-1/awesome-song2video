# 数据模型 — 渲染 Worker 并行异步裁剪

## 1. RenderJob（现有实体扩展）
- **位置**：`src/domain/models/song_mix.py`
- **新增字段**：
  - `metrics.render.clip_stats.total_tasks` (int, ≥0) — 本次裁剪任务总数。
  - `metrics.render.clip_stats.success_tasks` (int, ≥0, ≤total)
  - `metrics.render.clip_stats.failed_tasks` (int, ≥0, ≤total)
  - `metrics.render.clip_stats.avg_task_duration_ms` (float, ≥0)
  - `metrics.render.clip_stats.p95_task_duration_ms` (float, ≥0)
  - `metrics.render.clip_stats.peak_parallelism` (int, ≥1)
  - `metrics.render.clip_stats.placeholder_tasks` (int, ≥0)
  - `metrics.render.clip_stats.generated_at` (datetime, UTC)
- **约束**：`success_tasks + failed_tasks == total_tasks`；若 `placeholder_tasks > 0`，需保证 `failed_tasks ≥ placeholder_tasks`。
- **关系**：RenderJob ↔ SongMixRequest（1:1）。clip_stats 仅在渲染成功或失败时写入一次。

## 2. ClipDownloadTask（虚拟实体，用于日志/指标）
- **位置**：由 `render_worker` 运行期生成，不持久化。
- **字段**：
  - `clip_task_id` (uuid4)
  - `render_job_id` (uuid reference)
  - `line_id` (uuid，来源歌词行)
  - `video_id` (str)
  - `start_time_ms` / `end_time_ms` (int, end > start)
  - `parallel_slot` (int, 0-based)
  - `retry_count` (int, ≥0)
  - `status` (enum: pending/running/success/fallback-local/fallback-placeholder/failed)
  - `started_at` / `finished_at` (datetime UTC)
  - `source_type` (enum: hls/local/placeholder)
  - `error_code` (optional str)
- **用途**：
  - 写入 `twelvelabs.video_clip` 日志与 Prometheus counters。
  - 统计 `clip_stats` 时作为中间态输入。

## 3. RenderClipConfig（运行时配置映射）
- **字段**：
  - `max_parallelism` (int, 默认 4，范围 1~6)
  - `per_video_limit` (int, 默认 2)
  - `max_retry` (int, 默认 2)
  - `placeholder_asset_path` (str, 例如 `media/fallback/clip_placeholder.mp4`)
  - `retry_backoff_base_ms` (int, 默认 500)
  - `metrics_flush_interval_s` (int, 默认 5)
- **约束**：由 Redis Pub/Sub 广播；收到消息后需校验数值范围，非法配置忽略并写日志。
- **关系**：被 render worker 读取；不会写入数据库。

## 状态转换
1. ClipDownloadTask 状态流：pending → running → (success | fallback-local | fallback-placeholder | failed)。失败状态会写入 RenderJob.clip_stats 并触发占位片段逻辑。
2. RenderJob 状态保持 queued → running → (success | failure)，clip_stats 在 running 结束时填充。

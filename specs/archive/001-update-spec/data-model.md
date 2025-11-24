# 数据模型：需求与实现对齐更新

## SongMixRequest

- **角色**：一次混剪任务的主记录，聚合歌词 ingest、匹配、审核、渲染。
- **新增/强化字段**：
  - `metrics.preview (jsonb)`：结构固定为
    ```json
    {
      "line_count": int,
      "total_duration_ms": int,
      "avg_delta_ms": float,
      "max_delta_ms": float,
      "fallback_count": int,
      "generated_at": "2025-11-13T11:30:00Z"
    }
    ```
  - `metrics.render (jsonb)`：写入最新渲染任务的聚合指标（见 RenderMetrics）。
  - `timeline_status`、`render_status`：需与 worker 推进保持一致（`generated/in_review/locked/queued/running/success/failed`）。
- **规则**：
  - `metrics.preview` 必须在 timeline builder 成功后写入；缺失时 preview API 返回 404。
  - `render_status=success` 时 `metrics.render`、`render_jobs.output_asset_id` 均需存在。

## PreviewManifestEntry（非持久化 DTO）

- **字段**：`line_id`、`line_no`、`lyrics`、`source_video_id`、`clip_start_ms`、`clip_end_ms`、`confidence`、`fallback (bool)`、`fallback_reason (str|null)`。
- **来源**：由 `LyricLine` + `VideoSegmentMatch` 组合生成；fallback 时 `source_video_id` 采用 `settings.fallback_video_id`。
- **校验**：`clip_start_ms < clip_end_ms`；当 `fallback=true` 时 `confidence` 强制为 0。

## LyricLine

- **新增字段**：运行时 `candidates: list[VideoSegmentMatch]` 继续由仓储层注入；`selected_segment_id` 决定渲染片段。
- **规则**：
  - `status=locked` 的行才会被 render worker 消费。
  - 为计算对齐偏差，需确保 `start/end_time_ms` 与音频节奏一致。

## VideoSegmentMatch

- **补充字段**：`generated_by`（enum: auto|rerank|manual|fallback）、`tags`（json）、`score`。
- **规则**：
  - 每行最多保留 10 条候选；`generated_by=fallback` 表示无 TwelveLabs 命中。
  - 在 manifest 中仅选取选中候选或置信度最高者。

## RenderJob

- **核心字段**：`id`、`mix_request_id`、`job_status`、`output_asset_id`、`ffmpeg_script`、`metrics.render (jsonb)`、`created_at/updated_at`。
- **规则**：
  - `job_status` 需按 `queued → running → success|failed` 更新。
  - `metrics.render` 写入 `_calculate_alignment` 结果，并附加 `queued_at`、`finished_at` 时间戳。

## RenderMetrics（嵌入 RenderJob.metrics.render）

- **结构**：
  ```json
  {
    "line_count": int,
    "avg_delta_ms": float,
    "max_delta_ms": float,
    "total_duration_ms": int,
    "queued_at": "2025-11-13T10:59:10Z",
    "finished_at": "2025-11-13T11:00:05Z"
  }
  ```
- **来源**：`render_worker._calculate_alignment` + 任务生命周期记录。
- **用途**：供 API/Prometheus 暴露渲染健康度，并在日志中复用该结构。

## 指标字段与可观测性

- `metrics.preview.fallback_count`：统计需要 fallback 的歌词行数，用于缺失媒资提醒。
- 通过 OTEL 导出 `lyrics_preview_avg_delta_ms`、`render_alignment_max_delta_ms` 等 Gauge，Label 包含 `mix_id`、`job_id`、`owner_id`。
- structlog 日志字段统一：`preview.manifest_built`、`timeline_builder.candidates`、`render_worker.storage_todo`，方便 Loki 查询。

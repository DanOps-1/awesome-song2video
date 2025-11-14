# Preview & Render 指标监控文档

## 概述

本文档说明歌词混剪系统的 Preview 和 Render 阶段指标采集、查询与报警配置。

## 指标列表

### Preview 指标

| 指标名称 | 类型 | 单位 | 说明 | Label |
|---------|------|------|------|-------|
| `lyrics_preview_avg_delta_ms` | Gauge | ms | 歌词时长与视频片段的平均对齐偏差 | mix_id, owner_id |
| `lyrics_preview_max_delta_ms` | Gauge | ms | 最大对齐偏差 | mix_id, owner_id |
| `lyrics_preview_fallback_count` | Counter | lines | 使用 fallback 视频的歌词行数 | mix_id, owner_id |
| `lyrics_preview_line_count` | Gauge | lines | Preview manifest 中的歌词行总数 | mix_id, owner_id |

### Render 指标

| 指标名称 | 类型 | 单位 | 说明 | Label |
|---------|------|------|------|-------|
| `render_alignment_avg_delta_ms` | Gauge | ms | 渲染完成后的平均对齐偏差 | job_id, mix_id, owner_id |
| `render_alignment_max_delta_ms` | Gauge | ms | 渲染完成后的最大对齐偏差 | job_id, mix_id, owner_id |
| `render_total_duration_ms` | Gauge | ms | 渲染任务从队列到完成的总耗时 | job_id, mix_id, owner_id |
| `render_queue_depth` | Gauge | jobs | 当前等待渲染的任务数 | - |

## Prometheus 查询示例

### Preview 相关

```promql
# 所有 mix 的平均对齐偏差
avg(lyrics_preview_avg_delta_ms)

# 对齐偏差超过 200ms 的 mix 数量
count(lyrics_preview_avg_delta_ms > 200)

# 按 owner 分组的 fallback 总数
sum(lyrics_preview_fallback_count) by (owner_id)

# 最近 1 小时内生成的 manifest 平均行数
avg_over_time(lyrics_preview_line_count[1h])
```

### Render 相关

```promql
# 最近 5 分钟渲染任务的平均对齐质量
avg_over_time(render_alignment_avg_delta_ms[5m])

# 渲染队列深度趋势
render_queue_depth

# 渲染任务总耗时 95 分位数
histogram_quantile(0.95, sum(rate(render_total_duration_ms_bucket[5m])) by (le))

# 对齐质量不佳的渲染任务 (平均偏差 > 500ms)
count(render_alignment_avg_delta_ms > 500)
```

## Loki 日志查询示例

### Preview 日志

```logql
# Preview manifest 生成事件
{job="lyrics-mix-api"} |= "preview.manifest_built" | json

# Fallback 使用警告
{job="lyrics-mix-api"} |= "preview.fallback_used" | json | line_format "{{.line_no}}: {{.fallback_reason}}"

# Preview API 调用
{job="lyrics-mix-api"} |= "preview.api.get_manifest" | json | line_format "mix_id={{.mix_id}}"
```

### Render 日志

```promql
# Render worker 队列深度
{job="lyrics-mix-worker"} |= "render_worker.queue_depth" | json

# MinIO 上传 TODO 警告
{job="lyrics-mix-worker"} |= "render_worker.storage_todo" | json | line_format "{{.local_path}}"

# 渲染任务完成事件
{job="lyrics-mix-worker"} |= "render_worker.completed" | json
```

## 报警规则

### Preview 报警

```yaml
groups:
  - name: preview_alerts
    rules:
      - alert: HighPreviewDelta
        expr: lyrics_preview_avg_delta_ms > 500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Preview 对齐偏差过高"
          description: "Mix {{ $labels.mix_id }} 的平均对齐偏差为 {{ $value }}ms，超过 500ms 阈值"

      - alert: HighFallbackRate
        expr: sum(rate(lyrics_preview_fallback_count[5m])) / sum(rate(lyrics_preview_line_count[5m])) > 0.3
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Fallback 比例过高"
          description: "Fallback 行占比 {{ $value | humanizePercentage }}，可能 TwelveLabs 检索质量下降"
```

### Render 报警

```yaml
groups:
  - name: render_alerts
    rules:
      - alert: RenderQueueBacklog
        expr: render_queue_depth > 10
        for: 15m
        labels:
          severity: critical
        annotations:
          summary: "渲染队列积压严重"
          description: "当前队列深度 {{ $value }} 个任务，持续 15 分钟未消化"

      - alert: RenderAlignmentDegraded
        expr: render_alignment_avg_delta_ms > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "渲染对齐质量下降"
          description: "Job {{ $labels.job_id }} 对齐偏差 {{ $value }}ms，超过 1000ms"
```

## 仪表盘配置

参见 `observability/dashboards/lyrics_mix.json`，已包含：

- Preview 平均/最大对齐偏差趋势图
- Fallback 行数统计
- Render 对齐质量分布
- 渲染队列深度实时监控
- Loki 日志标注（Preview 生成事件、Render 存储 TODO、Fallback 使用）

## 成功标准

### SC-001: Preview 对齐质量

- **目标**: 平均对齐偏差 ≤ 200ms
- **验证**: `avg(lyrics_preview_avg_delta_ms) <= 200`

### SC-002: Render 对齐质量

- **目标**: 平均对齐偏差 ≤ 200ms
- **验证**: `avg(render_alignment_avg_delta_ms) <= 200`

### SC-003: 指标可用性

- **目标**: Preview/Render 指标 5 分钟内可在 Prometheus 查询
- **验证**: 执行上述查询确认有数据返回

### SC-004: Fallback 追踪

- **目标**: Fallback 行数和原因可通过 API 和日志查询
- **验证**:
  - API: `GET /api/v1/mixes/{mix_id}/preview` 返回 `metrics.fallback_count`
  - Loki: 查询 `preview.fallback_used` 事件

## 故障排查

### 指标未上报

1. 检查 OTEL Exporter 配置：`echo $OTEL_EXPORTER_OTLP_ENDPOINT`
2. 查看 structlog 日志确认 `preview.manifest_built` 和 `render_worker.completed` 事件
3. 确认 Prometheus 抓取配置中包含应用端点

### 对齐偏差异常

1. 查询具体 mix: `lyrics_preview_avg_delta_ms{mix_id="xxx"}`
2. 检查 Loki 日志中的 fallback 警告
3. 验证 TwelveLabs 候选质量

### 渲染队列积压

1. 检查 worker 并发限制：`echo $RENDER_CONCURRENCY`
2. 查看 `render_worker.queue_depth` 日志
3. 确认 FFmpeg 执行时长是否异常

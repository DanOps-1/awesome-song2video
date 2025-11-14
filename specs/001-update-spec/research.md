# Research Log：001-update-spec

## 主题：时间线 manifest 字段扩展
- **Decision**：Manifest 统一返回 `line_id/lyrics/source_video_id/clip_*_ms/confidence/fallback`，并同步 `SongMixRequest.metrics.preview` 内的 `line_count/total_duration_ms/avg_delta_ms/max_delta_ms/fallback_count/generated_at`。
- **Rationale**：策划审核需要字段齐全才能定位缺失片段；同时 metrics 直接提供对齐差值，便于成功标准 SC-001/002 的监控。
- **Alternatives considered**：
  1. 继续直接返回数据库字段——无法体现 fallback 标记。
  2. 仅在日志打印指标——无法给前端/Prometheus 消费。
  3. 新建独立 metrics 表——迭代成本高，复用 `SongMixRequest.metrics` 更快。

## 主题：TwelveLabs 未命中时的 fallback 处理
- **Decision**：优先使用配置中的 `fallback_video_id` + 对应 B-roll 时间段；Manifest 和日志需要写入 `fallback: true` 与缺失原因，`metrics.preview.fallback_count` 累加。
- **Rationale**：当前只有单一 demo 视频（`6911acda8bf751b791733149`），无命中行必须借助 fallback 才能渲染，且媒资管理员需要可追踪路径。
- **Alternatives considered**：
  1. 直接丢弃歌词行——导致渲染空白，不符合用户故事 3。
  2. 自动复制前一片段——会破坏语义节奏且难以审计。
  3. 立刻接入 MinIO/S3 ——尚无可用集群，转为 TODO 并保留本地路径。

## 主题：渲染指标与上传策略
- **Decision**：Render worker 在 `_calculate_alignment` 结果基础上扩展 `queued_at/finished_at`、`line_count/avg_delta_ms/max_delta_ms/total_duration_ms`，写入 `RenderJob.metrics.render`，并通过 structlog + OTEL 导出；产物上传仍以 TODO 记录，暴露本地文件位置。
- **Rationale**：渲染对齐指标是 SC-002 的硬性指标；MinIO 未启用时仍需成功交付视频，warning 可以提醒后续人工上传。
- **Alternatives considered**：
  1. 改为阻塞等待 MinIO ——会导致任务全部失败。
  2. 只写日志不更新数据库 ——运维无法通过 API 查询指标。
  3. 引入新 worker 专门算指标 ——复杂度与收益不匹配。

## 主题：可观测性落地
- **Decision**：沿用 structlog JSON 日志 + OTEL Exporter，将 preview/render 指标同步到 Prometheus（指标名 `lyrics_preview_*`、`render_alignment_*`），并在 Loki 中保留 manifest/fallback 事件。
- **Rationale**：宪章要求所有关键流程有指标与可追溯日志；现有三元组合（structlog + OTEL + Loki/Prom）已稳定，无需引入新栈。
- **Alternatives considered**：
  1. 使用 StatsD ——栈内无统一 collector。
  2. 仅依赖日志 ——无法支撑仪表盘。
  3. 引入商业 APM ——与当前自托管方案重复。

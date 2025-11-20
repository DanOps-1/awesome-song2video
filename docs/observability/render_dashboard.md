# 渲染并行裁剪指标面板

## 指标来源
- `render_clip_inflight`：当前进行中的剪辑任务数，Labels：`job_id`、`video_id`。
- `render_clip_failures_total`：剪辑失败累积次数，Labels：`job_id`、`video_id`、`reason`。
- `render_clip_duration_ms`：剪辑耗时直方图，Labels：`job_id`、`video_id`。
- `render_alignment_avg_delta_ms` / `render_alignment_max_delta_ms`：沿用既有渲染对齐指标。

## Grafana 面板建议
1. **Clip 并发槽位**：`render_clip_inflight` 按 `job_id` 聚合，显示当前值与峰值。
2. **失败原因分布**：`increase(render_clip_failures_total[5m])` 堆叠条形图，观察 5 分钟内各 `reason`。
3. **P95 裁剪耗时**：`histogram_quantile(0.95, sum(rate(render_clip_duration_ms_bucket[5m])) by (le))`。
4. **Clip 成功率**：结合 `render_jobs.metrics.render.clip_stats` 计算 `1 - failed/total`，在表格中展示。

## 告警建议
- `render_clip_inflight > render_clip_concurrency + 1` 连续 1 分钟触发告警。
- 任意 `reason="clip_not_generated"` 在 5 分钟内超过 5 次，提示 SRE 检查 TwelveLabs API。

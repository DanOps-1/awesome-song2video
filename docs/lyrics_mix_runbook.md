# 歌词语义混剪运行手册

> **更新日期**: 2025-11-13
> **版本**: 001-update-spec 实施完成
> **新增内容**: Preview Manifest API、Render Metrics、Fallback 追踪

## 部署步骤

1. **准备环境变量**：复制 `.env.example` → `.env`，通过密钥管理系统写入 `TL_API_KEY`、数据库与对象存储凭据。
2. **必填配置项**:
   - `TL_API_KEY`: TwelveLabs API 密钥
   - `TL_INDEX_ID`: TwelveLabs 索引 ID
   - `FALLBACK_VIDEO_ID`: Fallback 视频 ID (默认 `6911acda8bf751b791733149`)
   - `DATABASE_URL`: PostgreSQL 连接 URL
   - `REDIS_URL`: Redis 连接 URL
3. **数据库迁移**：执行 `alembic upgrade head`，确认建表成功。
4. **启动服务**：
   - `uvicorn src.api.main:app --host 0.0.0.0 --port 8080`
   - `arq src.workers.timeline_worker.WorkerSettings`
   - `arq src.workers.render_worker.WorkerSettings`
5. **配置监控**：部署 OTLP Collector，指向 `OTEL_EXPORTER_OTLP_ENDPOINT`，在 Prometheus/Loki 中导入 `observability/dashboards/lyrics_mix.json`。

## 运行流程

1. 通过 `POST /api/v1/mixes` 上传音频或歌词。
2. 调用 `POST /api/v1/mixes/{mix_id}/generate-timeline`，等待 US1 自动匹配完成；若 `ENABLE_ASYNC_QUEUE=true`，该步骤会投递 Arq 任务，否则在 API 线程中立即执行。
3. 使用 `GET /api/v1/mixes/{mix_id}/lines` + `PATCH /...` 进行人工校对，可通过 `POST /lines/{line_id}/search` 重新触发 TwelveLabs 检索。
4. 全部歌词 `locked` 后，提交 `POST /api/v1/mixes/{mix_id}/render`，轮询 `GET .../render` 直至 `success`。渲染 Worker 将按照 `VIDEO_ASSET_DIR`（或 MinIO）加载素材并调用 FFmpeg 组合输出 MP4 + SRT。

## 告警与排查

- **转写/匹配失败**：在 timeline worker 日志中查找 trace_id，确认 Whisper/TwelveLabs 配额与网络状态。
- **渲染耗时过长**：检查 render worker 日志，确认是否绑定 GPU 节点；必要时调整 `render_mix` 并发与队列优先级。
- **对象存储错误**：确认 MinIO bucket 是否存在、凭据是否有效。

## Trace 与指标

### 关键指标 (新增)

**Preview 指标**:
- `lyrics_preview_avg_delta_ms`: 歌词与视频片段的平均对齐偏差
- `lyrics_preview_max_delta_ms`: 最大对齐偏差
- `lyrics_preview_fallback_count`: Fallback 行数
- `lyrics_preview_line_count`: 歌词行总数

**Render 指标**:
- `render_alignment_avg_delta_ms`: 渲染后的平均对齐偏差
- `render_alignment_max_delta_ms`: 渲染后的最大对齐偏差
- `render_total_duration_ms`: 渲染任务总耗时
- `render_queue_depth`: 当前队列深度

**传统指标**:
- `lyrics_parse_latency`: 歌词解析延迟
- `match_hit_rate`: 匹配命中率
- `render_duration`: 渲染耗时
- `api_error_rate`: API 错误率

详细监控配置参见：`docs/metrics/preview_render.md`

## 手动干预

- **重试渲染**：调用 `POST /api/v1/mixes/{mix_id}/render` 重新生成 job，并在后台清理旧的 RenderJob 记录。
- **替换素材**：在校对阶段通过 `POST /lines/{line_id}/search` 重检索片段，或在 `VIDEO_ASSET_DIR` 中放置同名 `mp4` 供渲染 Worker 使用。

## 真实 TwelveLabs / FFmpeg 集成提示

- **启用真实匹配**：设置 `TL_ENABLE_LIVE=true` 后，`TimelineBuilder` 将使用 TwelveLabs SDK；若调用失败，会自动降级到本地 mock 并在日志中标记 `twelvelabs.search_failed`。
- **本地素材映射**：`source_video_id` 会按照 `<video_asset_dir>/<video_id>.mp4` 查找文件（示例：`tom` → `media/video/tom.mp4`）。若使用 MinIO，请确保相同命名的对象存在。
- **FFmpeg 依赖**：Worker 默认调用系统 `ffmpeg`。如需不同路径，可在部署脚本中调整 `PATH` 或将命令改写为绝对路径。
- **队列模式**：`ENABLE_ASYNC_QUEUE=true` 时需要运行 Redis + Arq Worker；本地调试可保持 `false`，API 将直接调用 Worker 函数。

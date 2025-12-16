# 功能演示指南

**版本**: v2.0
**最后更新**: 2025-12-16

本文档包含系统主要功能的演示步骤，涵盖歌词获取、节拍分析、视频匹配、渲染等核心流程。所有命令均在项目根目录执行，假设 `.venv` 已安装 `.[dev]` 依赖。

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

---

## Demo 4：歌词获取演示

**目标**：演示多源歌词获取功能，包括 QQ 音乐、网易云、酷狗、LRCLIB 的自动降级。

### 步骤
1. 命令行测试歌词获取：
   ```bash
   python -m src.lyrics.fetcher "夜曲" "周杰伦"
   ```
2. 预期输出：
   ```text
   [INFO] 尝试从 QQ Music 获取歌词...
   [INFO] 成功获取歌词，来源: qq_music
   [INFO] 歌词行数: 42
   ```
3. API 调用测试：
   ```bash
   # 创建 mix
   curl -X POST http://localhost:8000/api/v1/mixes \
     -H "Content-Type: application/json" \
     -d '{"song_title": "夜曲", "artist": "周杰伦", "audio_asset_id": "test.mp3"}'

   # 获取歌词
   curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/fetch-lyrics
   ```
4. 查看歌词行：
   ```bash
   curl http://localhost:8000/api/v1/mixes/{mix_id}/lines | jq '.lines | length'
   ```

### 通过标准
- 歌词成功获取且包含时间戳
- 支持中文、日文、英文歌曲
- 自动降级到下一个平台（如 QQ 失败则尝试网易云）

---

## Demo 5：节拍分析与同步

**目标**：演示音频节拍检测和视频片段节拍对齐功能。

### 步骤
1. 创建 mix 并上传音频后，触发节拍分析：
   ```bash
   curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/analyze-beats
   ```
2. 查看节拍分析结果：
   ```bash
   curl http://localhost:8000/api/v1/mixes/{mix_id}/beats | jq
   ```
   预期输出：
   ```json
   {
     "bpm": 120.5,
     "beat_times": [0.5, 1.0, 1.5, ...],
     "downbeats": [0.5, 2.5, 4.5, ...],
     "tempo_stability": 0.95
   }
   ```
3. 开启节拍同步：
   ```bash
   curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/beat-sync \
     -H "Content-Type: application/json" \
     -d '{"enabled": true}'
   ```
4. 配置节拍同步模式（onset=鼓点对齐，action=动作点对齐）：
   ```bash
   # 在 .env 中设置
   BEAT_SYNC_MODE=onset
   BEAT_SYNC_MAX_ADJUSTMENT_MS=500
   ```

### 通过标准
- BPM 检测准确（误差 < 5%）
- 节拍时间点与音频节奏一致
- 渲染后视频切换与节拍同步

---

## Demo 6：端到端完整流程

**目标**：演示从上传音频到渲染完成的完整流程。

### 步骤
1. 创建混剪任务：
   ```bash
   curl -X POST http://localhost:8000/api/v1/mixes \
     -H "Content-Type: application/json" \
     -d '{
       "song_title": "测试歌曲",
       "artist": "测试歌手",
       "audio_asset_id": "media/uploads/test.mp3"
     }'
   ```
2. 获取歌词（选择一种方式）：
   ```bash
   # 方式 A: 在线获取
   curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/fetch-lyrics

   # 方式 B: Whisper 识别
   curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/transcribe

   # 方式 C: 手动导入
   curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/import-lyrics \
     -H "Content-Type: application/json" \
     -d '{"lyrics_text": "[00:00.00]第一句歌词\n[00:05.00]第二句歌词"}'
   ```
3. 等待视频匹配完成：
   ```bash
   # 查看任务状态
   curl http://localhost:8000/api/v1/mixes/{mix_id} | jq '.timeline_status'
   ```
4. 预览匹配结果：
   ```bash
   curl http://localhost:8000/api/v1/mixes/{mix_id}/preview | jq
   ```
5. 提交渲染：
   ```bash
   curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/render \
     -H "Content-Type: application/json" \
     -d '{"resolution": "1080p", "aspect_ratio": "16:9"}'
   ```
6. 查看渲染进度：
   ```bash
   curl http://localhost:8000/api/v1/mixes/{mix_id} | jq '.render_status'
   ```

### 通过标准
- 全流程无手动干预完成
- 渲染视频与音频同步
- 字幕正确显示

---

## Demo 附录：命令速查

| 目的 | 命令 |
| --- | --- |
| 启动所有服务 | `bash start.sh` |
| 测试歌词获取 | `python -m src.lyrics.fetcher "歌名" "歌手"` |
| 并行渲染回归 | `pytest tests/integration/render/test_parallel_clip_pipeline.py` |
| 占位回退回归 | `pytest tests/integration/render/test_render_fallbacks.py` |
| 渲染配置契约 | `pytest tests/contract/api/test_render_config.py` |
| 生成占位素材 | `python scripts/media/create_placeholder_clip.py` |
| 触发热加载 | `redis-cli publish render:config '{"max_parallelism":6,...}'` |
| 端到端测试 | `python scripts/dev/e2e_full_render_test.py` |
| 代码检查 | `ruff check src tests && mypy src` |

> **提示**：所有指标面板位于 `docs/observability/render_dashboard.md`，包含 `render_clip_inflight`、`render_clip_placeholder_total`、`render_clip_failures_total`、`render_clip_duration_ms` 的 Grafana 图表说明。

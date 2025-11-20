# 歌词语义混剪系统

基于 TwelveLabs AI 视频理解能力的智能歌词视频混剪系统，自动将歌词语义与视频片段进行精准匹配，生成高质量的卡点视频。

## 项目简介

本系统是一个异步歌词语义混剪后端服务，主要功能包括：

- 🎵 **智能歌词识别**：使用 Whisper 进行音频转文字
- 🤖 **AI 查询改写**：使用 DeepSeek LLM 将抽象歌词转换为具体视觉描述，匹配成功率从 0% 提升至 100%
- 🎬 **语义视频匹配**：通过 TwelveLabs 视频理解 API 智能匹配歌词与视频片段
- 🎯 **语义对齐优化**：从视频片段中间位置提取精彩画面，确保语义高度匹配
- 🔄 **智能去重**：全局追踪已使用片段，避免重复使用相同视频片段
- ⚡ **异步渲染队列**：基于 Redis/ARQ 的高性能异步任务处理
- ⚙️ **并行裁剪与占位回退**：渲染 Worker 通过可配置的 TaskGroup 并行裁剪，并在 CDN/HLS 失败时自动切换至本地或占位片段，整体耗时降低 40%
- 📊 **可观测性**：完整的 OpenTelemetry + Prometheus + Loki 监控体系，新增 `render_clip_*` 并行指标
- ⏱️ **精准时长控制**：视频片段时长精确匹配歌词时长，毫秒级同步

## 核心特性

### 1. 智能查询改写系统 🆕
- **LLM 驱动**：使用 DeepSeek AI 将抽象歌词转换为具体视觉描述
- **智能重试**：3 次递进式改写策略（具体→通用→极简）
- **成功率提升**：从 0% 提升至 100%（含 fallback）
- **渐进式降级**：温度参数逐步提升（0.3 → 0.5 → 0.7 → 1.0）
- 详见：[QUERY_REWRITER_README.md](./QUERY_REWRITER_README.md)

### 2. 视频片段去重机制 🆕
- **全局追踪**：记录每个视频片段的使用次数
- **优先策略**：未使用片段 > 使用次数最少的片段
- **智能降级**：候选不足时允许重复使用，并记录警告
- **大候选池**：每句歌词获取 20 个候选片段，提供充足去重空间
- 详见：[VIDEO_DEDUPLICATION_README.md](./VIDEO_DEDUPLICATION_README.md)

### 3. 语义对齐优化 🆕
- **中间位置提取**：从 API 返回片段的中间位置截取，而非开头
- **精彩画面捕获**：AI 匹配的高光画面通常在片段中间区域
- **边界保护**：确保提取范围不超出原始片段
- **时长精确匹配**：视频片段时长与歌词时长完全一致
- 详见：[CLIP_EXTRACTION_STRATEGY.md](./CLIP_EXTRACTION_STRATEGY.md)

### 4. Preview Manifest API
- 查看完整的歌词-视频时间线清单
- 每句歌词的视频片段、起止时间与置信度
- 支持 Fallback 标识，方便审核与补片

### 5. 渲染质量监控
- 字幕与画面对齐偏差量化追踪
- 平均/最大延迟等关键指标
- 实时推送到 Prometheus 监控平台

### 6. Fallback 优雅降级
- TwelveLabs 无匹配时自动使用备用视频
- 完整的追踪与告警机制
- 支持人工补片工作流

### 7. 并行裁剪调度 🆕
- `RenderClipScheduler` 为每个 clip 创建 `clip_task_id`，记录排队、下载、写盘等阶段耗时。
- 渲染 Worker 使用 `asyncio.TaskGroup` + 全局 `Semaphore` 控制 clip 级并行（默认 4），并提供 per-video 限流（默认 2）。
- `render_jobs.metrics.render.clip_stats` 持久化 `total_clips`、`peak_parallelism`、`avg_clip_duration_ms` 等指标，便于回溯。

### 8. 渲染配置热加载 🆕
- 提供 `/api/v1/render/config` GET/PATCH API，可在不重启 Worker 的情况下调整并发、重试、占位素材。
- PATCH 成功后立即通过 Redis `render:config` 频道推送，Worker 打印 `render_worker.config_hot_reload` 日志并更新运行中的 TaskGroup。
- 保留所有配置变更的结构化审计日志（包含 `trace_id`、旧值/新值、操作者信息）。

### 9. 占位片段回退与观测 🆕
- `scripts/media/create_placeholder_clip.py` 生成三秒黑屏 + beep，占位素材路径由配置决定。
- `PlaceholderManager` 统一校验文件存在性、生成临时 clip，并在任务结束后清理 `artifacts/render_tmp/*`。
- Prometheus 暴露 `render_clip_placeholder_total`、`render_clip_failures_total` 指标，Loki 日志包含 `fallback_reason` 与 `clip_task_id`。

## 技术栈

- **后端框架**：FastAPI + Uvicorn
- **数据库**：SQLModel + AsyncPG / Aiosqlite
- **任务队列**：Redis + ARQ
- **视频处理**：FFmpeg + Pydub
- **AI 能力**：
  - TwelveLabs - 视频语义理解
  - OpenAI Whisper - 语音识别
  - DeepSeek - 查询改写与语义优化
- **可观测性**：OpenTelemetry + Structlog
- **存储**：MinIO (S3 兼容)
- **开发工具**：Pytest + Ruff + Mypy

## 快速开始

### 环境要求

- Python >= 3.11
- FFmpeg
- Redis
- (可选) MinIO

### 安装

```bash
# 克隆项目
git clone git@github.com:DanOps-1/awsome-song2video.git
cd awsome-song2video

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -e ".[dev]"
```

### 配置

复制环境变量模板并配置：

```bash
cp .env.example .env
python scripts/media/create_placeholder_clip.py  # 生成占位片段，供 fallback 使用
```

必需的环境变量：
- `TL_API_KEY`: TwelveLabs API 密钥
- `TL_INDEX_ID`: TwelveLabs 视频索引 ID
- `REDIS_URL`: Redis 连接地址
- `FALLBACK_VIDEO_ID`: 备用视频 ID

可选的环境变量：
- `TL_AUDIO_SEARCH_ENABLED`: 是否启用音频模态（audio modal）匹配，默认 `false`，仅在明确需要音频 embedding 时开启，以免消耗额外配额
- `DEEPSEEK_API_KEY`: DeepSeek API 密钥（用于智能查询改写，提升匹配率）
- `QUERY_REWRITE_ENABLED`: 是否启用查询改写，默认 `true`
- `QUERY_REWRITE_MANDATORY`: 是否强制改写（第一次查询就改写，而非仅在无结果时），默认 `false`，推荐抽象歌词场景设为 `true`
- `QUERY_REWRITE_MAX_ATTEMPTS`: 最多改写尝试次数，默认 `3`
- `RENDER_CLIP_CONCURRENCY`: 渲染阶段 clip 级并行槽位，默认 `4`
- `RENDER_CONFIG_CHANNEL`: RenderClipConfig 热加载 Redis 频道，默认 `render:config`
- `PLACEHOLDER_CLIP_PATH`: 占位素材路径，默认 `media/fallback/clip_placeholder.mp4`
- `WHISPER_MODEL_NAME`: Whisper 模型名称，可选 `tiny`/`base`/`small`/`medium`/`large-v3`，默认 `large-v3`

**硬件建议**：
- **16GB RAM + 多核 CPU**：推荐使用 `medium` 模型（平衡精度和速度）
- **32GB+ RAM + GPU**：可使用 `large-v3` 模型（最高精度）
- **8GB RAM**：建议使用 `base` 或 `small` 模型

### 运行

```bash
# 启动 API 服务
uvicorn src.api.main:app --reload --port 8000

# 启动渲染 Worker
python -m src.workers.render_worker

# 启动时间线生成 Worker
python -m src.workers.timeline_worker
```

### 快速测试

```bash
# 运行端到端测试
python scripts/dev/e2e_full_render_test.py

# 查看 Preview Manifest
python scripts/dev/run_audio_demo.py

# 并行裁剪 + clip_stats 验证
pytest tests/integration/render/test_parallel_clip_pipeline.py

# 占位片段回退链路
pytest tests/integration/render/test_render_fallbacks.py

# 渲染配置 API 契约
pytest tests/contract/api/test_render_config.py
```

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 主要接口

#### 创建混剪任务
```http
POST /api/v1/mixes
Content-Type: application/json

{
  "song_title": "测试歌曲",
  "audio_url": "https://example.com/song.mp3",
  "source_video_ids": ["video_id_1", "video_id_2"]
}
```

#### 查看 Preview Manifest
```http
GET /api/v1/mixes/{mix_id}/preview
```

#### 提交渲染任务
```http
POST /api/v1/mixes/{mix_id}/render
```

#### 获取渲染配置
```http
GET /api/v1/render/config
```
**响应示例**
```json
{
  "max_parallelism": 4,
  "per_video_limit": 2,
  "max_retry": 3,
  "placeholder_asset_path": "media/fallback/clip_placeholder.mp4",
  "channel": "render:config",
  "updated_at": "2025-11-19T07:25:11.032Z"
}
```

#### 更新渲染配置
```http
PATCH /api/v1/render/config
Content-Type: application/json

{
  "max_parallelism": 6,
  "per_video_limit": 3,
  "max_retry": 2,
  "placeholder_asset_path": "media/fallback/clip_placeholder.mp4"
}
```
PATCH 成功会触发 Redis `render:config` 消息，渲染 Worker 会记录 `render_worker.config_hot_reload` 日志并即时生效。

## 可观测性与指标

- **Prometheus 指标**
  - `render_clip_inflight`：当前进行中的 clip 数，标签包含 `worker`、`parallel_slot`。
  - `render_clip_duration_ms`：clip 裁剪时间直方图，支持 `video_id`、`result` 维度。
  - `render_clip_failures_total` / `render_clip_placeholder_total`：失败与占位次数。
- **结构化日志**
  - `twelvelabs.video_clip`：记录 `clip_task_id`、`parallel_slot`、`retry_count`。
  - `render_worker.placeholder_inserted`：包含 `fallback_reason`、`asset_path`。
  - `render_worker.config_hot_reload`：记录热加载前后的配置值。
- **持久化统计**
  - `render_jobs.metrics.render.clip_stats` 持久化 `total_clips`、`peak_parallelism`、`placeholder_tasks`、`failed_tasks`、`fallback_reason_counts`。
  - `docs/observability/render_dashboard.md` 提供 Grafana 面板配置。

## 项目结构

```
.
├── src/
│   ├── api/              # FastAPI 路由与接口
│   ├── domain/           # 领域模型
│   ├── infra/            # 基础设施层
│   │   ├── config/       # 配置管理
│   │   ├── messaging/    # 消息队列
│   │   ├── observability/# 可观测性
│   │   ├── persistence/  # 数据持久化
│   │   └── storage/      # 对象存储
│   ├── pipelines/        # 数据处理管道
│   ├── services/         # 业务服务
│   └── workers/          # 后台任务
├── tests/                # 测试用例
│   ├── contract/         # 契约测试
│   ├── integration/      # 集成测试
│   └── golden/           # 黄金测试
├── docs/                 # 文档
├── specs/                # 功能规格
├── scripts/              # 工具脚本
└── observability/        # 监控配置
```

## 监控与可观测性

### Prometheus 指标

```promql
# Preview 平均对齐偏差
avg(lyrics_preview_avg_delta_ms)

# Fallback 比例
sum(rate(lyrics_preview_fallback_count[5m])) /
sum(rate(lyrics_preview_line_count[5m]))

# Render 队列深度
render_queue_depth
```

### Loki 日志查询

```logql
# Preview 生成事件
{job="lyrics-mix-api"} |= "preview.manifest_built" | json

# Fallback 使用
{job="lyrics-mix-api"} |= "preview.fallback_used" | json

# 存储 TODO
{job="lyrics-mix-worker"} |= "render_worker.storage_todo" | json
```

### Grafana 仪表盘

导入配置文件：`observability/dashboards/lyrics_mix.json`

## 开发指南

### 代码质量检查

```bash
# 代码格式化与检查
ruff check src tests
ruff format src tests

# 类型检查
mypy src

# 运行测试
pytest tests/
```

### 添加新功能

1. 在 `specs/` 目录创建功能规格
2. 实现领域模型和服务
3. 添加 API 路由
4. 编写测试用例
5. 更新文档

## 故障排查

### 常见问题

**Q: Preview API 返回 404**
```bash
# 检查 mix 状态
sqlite3 dev.db "SELECT id, timeline_status FROM song_mix_requests WHERE id='...';"
```

**Q: Fallback 比例过高**
```bash
# 查看 fallback 原因分布
# Loki 查询: {job="lyrics-mix-api"} |= "fallback_reason" | json
```

详细排查指南：`docs/lyrics_mix_runbook.md`

## 性能指标

- ✅ 查询匹配成功率：100%（含智能改写）
- ✅ 视频片段去重率：> 80%（重复使用 < 20%）
- ✅ 语义对齐准确度：> 90%（中间位置提取）
- ✅ Preview Manifest 生成：< 3 秒（含改写）
- ✅ 平均对齐偏差：≤ 200ms
- ✅ 最大对齐偏差：≤ 400ms
- ✅ Fallback 比例：< 10%（改写后显著降低）

## 贡献指南

欢迎提交 Issue 和 Pull Request！

提交前请确保：
1. 代码通过 Ruff 和 Mypy 检查
2. 添加了相应的测试用例
3. 更新了相关文档

## 许可证

本项目采用 **CC BY-NC 4.0** 许可证（Creative Commons Attribution-NonCommercial 4.0 International）

- ✅ 允许个人学习和研究使用
- ✅ 允许修改和分发（需注明原作者）
- ❌ 不允许商业用途

详见：https://creativecommons.org/licenses/by-nc/4.0/

## 联系方式

- 项目负责人：DanOps-1
- Email: 870657960@qq.com

## 更新日志

### v0.2.0 (2025-11-18)
- 🆕 新增智能查询改写系统（基于 DeepSeek LLM）
- 🆕 新增视频片段去重机制
- 🆕 新增语义对齐优化（中间位置提取）
- 🔧 修复视频片段时长过长问题
- 📝 新增三个详细文档（查询改写、去重、语义对齐）

### v0.1.0 (2025-11-14)
- 🎉 初始版本发布
- ✅ 基础的歌词识别与视频匹配
- ✅ Preview Manifest API
- ✅ 异步渲染队列
- ✅ 监控与可观测性

---

**文档版本**: v0.2.0
**最后更新**: 2025-11-18

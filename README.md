# 歌词语义混剪系统

基于 TwelveLabs AI 视频理解能力的智能歌词视频混剪系统，自动将歌词语义与视频片段进行精准匹配，生成高质量的卡点视频。

## 项目简介

本系统是一个异步歌词语义混剪后端服务，主要功能包括：

- 🎵 **智能歌词识别**：使用 Whisper large-v3 进行音频转文字，支持自动跳过音乐前奏
- 🤖 **AI 查询改写**：使用 DeepSeek LLM 将抽象歌词转换为具体视觉描述，匹配成功率从 0% 提升至 100%
- 🎬 **语义视频匹配**：通过 TwelveLabs 视频理解 API 智能匹配歌词与视频片段
- 🎯 **语义对齐优化**：从视频片段中间位置提取精彩画面，确保语义高度匹配
- 🔄 **智能去重**：全局追踪已使用片段，避免重复使用相同视频片段
- ⚡ **异步渲染队列**：基于 Redis/ARQ 的高性能异步任务处理
- ⚙️ **并行裁剪与占位回退**：渲染 Worker 通过可配置的 TaskGroup 并行裁剪，并在 CDN/HLS 失败时自动切换至本地或占位片段，整体耗时降低 40%
- 📊 **可观测性**：完整的 OpenTelemetry + Prometheus + Loki 监控体系，新增 `render_clip_*` 并行指标
- ⏱️ **精准时长控制**：视频片段时长精确匹配歌词时长，毫秒级同步

## 核心特性

### 1. 视频比例与双语字幕 🆕

#### 1.1 视频比例选择
- **多比例支持**：支持 16:9（默认）和 4:3 输出视频
- **智能背景处理**：使用模糊背景方式处理不同比例视频，保持画面完整
- **用户可选**：在创建任务时选择输出视频比例

#### 1.2 双语字幕
- **中英双语**：支持同时显示中文原文和英文翻译
- **用户可选**：双语字幕为可选功能，默认仅显示原文
- **多翻译源**：集成免费翻译 API 作为备选方案

### 2. 智能音视频同步系统

#### 2.1 前奏检测与跳过
- **RMS 能量分析**：使用音频能量分析自动检测人声开始位置
- **自动跳过前奏**：检测到 >= 5 秒的纯音乐前奏时自动跳过，提升歌词识别准确率
- **精准时间戳**：自动调整时间戳偏移，确保字幕与原始音频完美同步
- **智能阈值**：使用 60th 百分位能量阈值，准确区分前奏和人声部分

**技术细节**：
- 0.5 秒窗口的 RMS 能量分析
- 只跳过 >= 5 秒的前奏，避免误判短开场
- 自动使用带后缀的临时文件避免冲突
- no_speech_prob 阈值可配置（默认 0.6），平衡片段数量和质量

#### 2.2 歌词片段细粒度优化
- **词级时间戳**：启用 Whisper word_timestamps 获取更细粒度的片段
- **片段数量提升**：从 26 个提升至 49-74 个（视歌曲而定）
- **画面更丰富**：更频繁的画面切换，每个片段 2-4 秒
- **禁用 Prompt**：移除 initial_prompt 避免 Whisper 合并短语

#### 2.3 音频裁剪与时间对齐
- **音频精准裁剪**：自动裁剪音频只保留歌词部分（从第一句到最后一句）
- **解决同步问题**：修复视频画面比音频提前的问题
- **字幕时间归零**：所有字幕时间从 00:00:00 开始（相对于第一个歌词）
- **三者完美对齐**：视频、音频、字幕时间轴完全同步

**工作原理**：
```
原始音频: |前奏12s|歌词213s|尾奏?|
          ↓ 裁剪
裁剪音频: |歌词213s|
视频片段: |clip1|clip2|...|clip74|
字幕时间: 00:00:00 → 03:33:28
```

**示例**：
- 检测到 12 秒前奏
- 音频从 12s 裁剪到 225.28s（保留 213.28 秒）
- 字幕从 00:00:00 开始（而非 00:00:12）
- 视频从 0s 开始播放，完美对齐音频

### 3. 智能查询改写系统
- **基于分数阈值的智能改写** 🆕：
  - 原始搜索 score >= 0.9 → 跳过改写（直白歌词）
  - 原始搜索 score < 0.9 → 触发改写 → 对比选择更好的结果（抽象歌词）
  - 避免直白歌词被过度改写干扰匹配
- **LLM 驱动**：使用 DeepSeek AI 将抽象歌词转换为具体视觉描述
- **Tom and Jerry 专属优化**：提示词针对卡通素材库定制
  - 策略 0：卡通场景转换（猫鼠追逐、躲藏、打斗等可视化场景）
  - 策略 1：动作强化模式（通用卡通动作关键词）
  - 策略 2：极简兜底（确保能搜到卡通画面）
- **智能重试**：最多 3 次递进式改写策略
- **渐进式降级**：温度参数逐步提升（0.3 → 0.5 → 0.7 → 1.0）
- 详见：[QUERY_REWRITER_README.md](./QUERY_REWRITER_README.md)

### 4. 视频片段去重机制
- **全局追踪**：记录每个视频片段的使用次数
- **优先策略**：未使用片段 > 使用次数最少的片段
- **智能降级**：候选不足时允许重复使用，并记录警告
- **大候选池**：每句歌词获取 20 个候选片段，提供充足去重空间
- 详见：[VIDEO_DEDUPLICATION_README.md](./VIDEO_DEDUPLICATION_README.md)

### 5. 素材视频片头过滤
- **自动跳过片头**：过滤视频开头 8 秒内的片段（片头标题画面）
- **可配置时长**：通过 `VIDEO_INTRO_SKIP_MS` 环境变量调整
- **日志追踪**：记录 `twelvelabs.intro_filtered` 事件，便于监控

### 6. 语义对齐优化
- **中间位置提取**：从 API 返回片段的中间位置截取，而非开头
- **精彩画面捕获**：AI 匹配的高光画面通常在片段中间区域
- **边界保护**：确保提取范围不超出原始片段
- **时长精确匹配**：视频片段时长与歌词时长完全一致
- 详见：[CLIP_EXTRACTION_STRATEGY.md](./CLIP_EXTRACTION_STRATEGY.md)

### 7. 鼓点自动卡点（类似剪映）
- **鼓点检测**：使用 librosa onset_detect 检测音频实际鼓点/冲击点
- **双模式支持**：
  - `onset` 模式（默认）：视频音频鼓点 → 音乐鼓点对齐
  - `action` 模式：视频画面动作点 → 音乐节拍对齐
- **智能偏移计算**：自动计算最佳时间偏移使鼓点对齐
- **5 候选容错**：每句歌词保留 5 个候选视频，渲染失败时自动回退
- **严格时长检查**：禁止视频循环，时长不足的候选直接丢弃

### 8. Preview Manifest API
- 查看完整的歌词-视频时间线清单
- 每句歌词的视频片段、起止时间与置信度
- 支持 Fallback 标识，方便审核与补片

### 9. 渲染质量监控
- 字幕与画面对齐偏差量化追踪
- 平均/最大延迟等关键指标
- 实时推送到 Prometheus 监控平台

### 10. Fallback 优雅降级
- TwelveLabs 无匹配时自动使用备用视频
- 完整的追踪与告警机制
- 支持人工补片工作流

### 11. 并行裁剪调度
- `RenderClipScheduler` 为每个 clip 创建 `clip_task_id`，记录排队、下载、写盘等阶段耗时。
- 渲染 Worker 使用 `asyncio.TaskGroup` + 全局 `Semaphore` 控制 clip 级并行（默认 4），并提供 per-video 限流（默认 2）。
- `render_jobs.metrics.render.clip_stats` 持久化 `total_clips`、`peak_parallelism`、`avg_clip_duration_ms` 等指标，便于回溯。

### 12. 渲染配置热加载
- 提供 `/api/v1/render/config` GET/PATCH API，可在不重启 Worker 的情况下调整并发、重试、占位素材。
- PATCH 成功后立即通过 Redis `render:config` 频道推送，Worker 打印 `render_worker.config_hot_reload` 日志并更新运行中的 TaskGroup。
- 保留所有配置变更的结构化审计日志（包含 `trace_id`、旧值/新值、操作者信息）。

### 13. 占位片段回退与观测
- `scripts/media/create_placeholder_clip.py` 生成三秒黑屏 + beep，占位素材路径由配置决定。
- `PlaceholderManager` 统一校验文件存在性、生成临时 clip，并在任务结束后清理 `artifacts/render_tmp/*`。
- Prometheus 暴露 `render_clip_placeholder_total`、`render_clip_failures_total` 指标，Loki 日志包含 `fallback_reason` 与 `clip_task_id`。

### 14. 实时日志查看（管理后台）🆕
- **日志查看 API**：`/api/v1/admin/logs` 系列接口
  - `GET /logs` - 查询历史日志，支持关键词和级别过滤
  - `GET /logs/stream` - 实时日志流（Server-Sent Events）
  - `GET /logs/files` - 列出可用日志文件
- **前端日志查看器**：管理后台 → 系统 → 实时日志
  - 实时日志流显示，支持暂停/继续
  - 关键词过滤和日志级别筛选
  - 快捷过滤按钮（beat, render, timeline, error, warning）
  - 自动滚动到最新日志

### 15. 节拍分析 API 🆕
- **手动触发分析**：`POST /api/v1/mixes/{id}/analyze-beats`
- **获取分析结果**：`GET /api/v1/mixes/{id}/beats`
  - BPM、节拍时间点、强拍位置、节奏稳定性
- **卡点开关控制**：`PATCH /api/v1/mixes/{id}/beat-sync`
  - 可为单个 Mix 启用或禁用卡点功能

## 技术栈

- **后端框架**：FastAPI + Uvicorn
- **前端框架**：React + TypeScript + Vite + TailwindCSS
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

- Python >= 3.10
- Node.js >= 18
- FFmpeg
- Redis
- (可选) MinIO

### 方式一：Miniconda 安装（推荐）

```bash
# 克隆项目
git clone git@github.com:DanOps-1/awsome-song2video.git
cd awsome-song2video

# 安装 Miniconda（如未安装）
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 创建 conda 环境
conda create -n song2video python=3.10 -y
conda activate song2video

# 安装后端依赖
pip install -e ".[dev]"

# 安装前端依赖
cd frontend && npm install && cd ..
cd web && npm install && cd ..
```

### 方式二：venv 虚拟环境安装

```bash
# 克隆项目
git clone git@github.com:DanOps-1/awsome-song2video.git
cd awsome-song2video

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装后端依赖
pip install -e ".[dev]"

# 安装前端依赖
cd frontend && npm install && cd ..
cd web && npm install && cd ..
```

### 方式三：Docker 启动

```bash
# 克隆项目
git clone git@github.com:DanOps-1/awsome-song2video.git
cd awsome-song2video

# 复制并配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入必要的 API 密钥

# 构建并启动
docker-compose up --build

# 或后台运行
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

**Docker 说明**：
- 默认运行 `scripts/dev/run_audio_demo.py` 演示脚本
- Whisper 模型会缓存到 Docker volume，避免重复下载
- 如需运行 API 服务，修改 `docker-compose.yml` 中的 command

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
- `QUERY_REWRITE_SCORE_THRESHOLD`: 触发改写的分数阈值，默认 `0.9`（原始搜索分数低于此值才改写）
- `QUERY_REWRITE_MAX_ATTEMPTS`: 最多改写尝试次数，默认 `3`
- `RENDER_CLIP_CONCURRENCY`: 渲染阶段 clip 级并行槽位，默认 `4`
- `RENDER_CONFIG_CHANNEL`: RenderClipConfig 热加载 Redis 频道，默认 `render:config`
- `PLACEHOLDER_CLIP_PATH`: 占位素材路径，默认 `media/fallback/clip_placeholder.mp4`
- `WHISPER_MODEL_NAME`: Whisper 模型名称，可选 `tiny`/`base`/`small`/`medium`/`large-v3`，默认 `large-v3`
- `WHISPER_NO_SPEECH_THRESHOLD`: Whisper 非语音阈值，默认 `0.6`，值越低过滤越严格（片段越多），值越高保留越多（片段越少）
- `BEAT_SYNC_ENABLED`: 是否启用节奏卡点，默认 `true`
- `BEAT_SYNC_MODE`: 卡点模式，`onset`（鼓点对齐，类似剪映）或 `action`（动作点对齐），默认 `onset`
- `BEAT_SYNC_MAX_ADJUSTMENT_MS`: 最大时间偏移（毫秒），默认 `500`
- `BEAT_SYNC_ONSET_TOLERANCE_MS`: 鼓点对齐容差（毫秒），默认 `80`

素材视频过滤：
- `VIDEO_INTRO_SKIP_MS`: 跳过视频开头的毫秒数（过滤片头标题画面），默认 `8000`
- `VIDEO_OUTRO_SKIP_MS`: 跳过视频结尾的毫秒数（过滤片尾画面），默认 `5000`（配置已定义，过滤逻辑待实现）

**硬件建议**：
- **16GB RAM + 多核 CPU**：推荐使用 `medium` 模型（平衡精度和速度）
- **32GB+ RAM + GPU**：可使用 `large-v3` 模型（最高精度）
- **8GB RAM**：建议使用 `base` 或 `small` 模型

### 运行

```bash
# 启动 API 服务（端口 8000）
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 启动渲染 Worker（可选，用于视频渲染）
python -m src.workers.render_worker

# 启动时间线生成 Worker（可选，用于异步任务）
python -m src.workers.timeline_worker

# 启动用户前端（端口 6008）
cd frontend && npm run dev -- --port 6008 --host 0.0.0.0

# 启动管理后台（端口 6006）
cd web && npm run dev -- --port 6006 --host 0.0.0.0
```

**后台运行（推荐）**：

```bash
# 后端 API
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/backend.log 2>&1 &

# 用户前端
cd frontend && npm run dev -- --port 6008 --host 0.0.0.0 > /tmp/user-frontend.log 2>&1 &

# 管理后台
cd web && npm run dev -- --port 6006 --host 0.0.0.0 > /tmp/admin-frontend.log 2>&1 &
```

### 访问地址

- **API 文档**: http://localhost:8000/docs
- **用户前端**: http://localhost:6008
- **管理后台**: http://localhost:6006

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
├── src/                  # 后端源代码
│   ├── api/              # FastAPI 路由
│   ├── audio/            # 音频处理 (节拍检测)
│   ├── domain/           # 领域模型
│   ├── infra/            # 基础设施层
│   ├── lyrics/           # 歌词获取
│   ├── pipelines/        # 处理管道
│   ├── retrieval/        # 视频检索
│   ├── services/         # 业务服务
│   └── workers/          # 后台任务
├── apps/                 # 前端应用
│   ├── frontend/         # 用户前端 (React)
│   └── web/              # 管理后台 (React)
├── tests/                # 测试用例
├── docs/                 # 文档
├── scripts/              # 工具脚本
├── deploy/               # 部署配置 (Docker)
├── requirements/         # Python 依赖
├── data/                 # 数据目录
├── media/                # 媒体文件
├── artifacts/            # 构建产物
└── logs/                 # 运行日志
```

## 监控与可观测性

### 日志系统 🆕

系统支持结构化日志，自动输出到文件和控制台：

**日志文件位置**：
- `logs/app.log` - 所有日志（JSON 格式），自动轮转（10MB × 5 个备份）
- `logs/error.log` - 错误日志（WARNING 及以上），自动轮转

**控制台输出**：
- 终端环境：彩色格式化输出（便于阅读）
- 非终端环境：JSON 格式（便于程序分析）

**日志特性**：
- 自动创建 `logs/` 目录
- 日志文件自动轮转（防止磁盘占满）
- JSON 格式便于日志分析和查询
- 支持异常堆栈追踪

**查看日志**：
```bash
# 实时查看所有日志
tail -f logs/app.log | jq .

# 实时查看错误日志
tail -f logs/error.log | jq .

# 过滤特定事件
cat logs/app.log | jq 'select(.event == "twelvelabs.search_query")'

# 统计错误数量
cat logs/error.log | jq -r '.event' | sort | uniq -c
```

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

# TwelveLabs 搜索查询
{job="lyrics-mix-api"} |= "twelvelabs.search_query" | json

# 视频去重跳过
{job="lyrics-mix-api"} |= "twelvelabs.skip_duplicate_video" | json
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

## 待实现

以下功能计划在后续版本中实现：

### 核心功能
- [ ] **视频片尾过滤**：实现 `VIDEO_OUTRO_SKIP_MS` 配置的过滤逻辑
  - 难点：TwelveLabs 搜索 API 返回的结果不包含视频总时长，无法判断片段是否在结尾区域
  - 可能方案：
    - A. 搜索时额外调用 Retrieve API 获取每个视频的元数据（增加 API 调用）
    - B. 预先缓存所有素材视频的时长元数据到数据库
    - C. 在渲染阶段过滤（使用 ffprobe 获取时长后判断）
- [ ] **去重逻辑优化**：优化视频片段去重算法，提升去重效率和准确度
- [ ] **Redis 校验**：添加 Redis 连接健康检查和数据一致性校验
- [ ] **非人声部分匹配乐器画面**：前奏、间奏、尾奏等非人声部分自动匹配乐器演奏画面

### 基础设施（明确 TODO 标记）

| 功能 | 文件位置 | 当前状态 |
|------|----------|----------|
| **MinIO 上传** | `src/workers/render_worker.py:193` | 仅打印日志，渲染产物只存本地无法分发 |
| **TwelveLabs 索引状态查询** | `src/api/v1/routes/admin/assets.py:203` | 返回硬编码 mock 状态，非真实 API 查询 |
| **TwelveLabs 重索引** | `src/api/v1/routes/admin/assets.py:226` | 空实现，仅返回占位响应 |
| **检索后端运行时切换** | `src/api/v1/routes/admin/config.py:183` | 仅返回提示信息，需手动改环境变量并重启 |

### 前端错误处理优化

当前 `frontend/src/pages/Status.tsx` 中所有 mutation 错误处理仅为 `console.error` + `alert`：

| 功能 | 行号 | 待优化 |
|------|------|--------|
| 更新歌词行 | 81 | 添加重试机制、详细错误展示 |
| 确认歌词 | 93 | 添加重试机制、详细错误展示 |
| 视频匹配 | 105 | 添加重试机制、详细错误展示 |
| 取消确认歌词 | 118 | 添加重试机制、详细错误展示 |
| 删除歌词行 | 132 | 添加重试机制、详细错误展示 |
| 添加歌词行 | 149 | 添加重试机制、详细错误展示 |
| 批量删除 | 164 | 添加重试机制、详细错误展示 |
| 锁定视频 | 179 | 添加重试机制、详细错误展示 |
| 提交渲染 | 191 | 添加重试机制、详细错误展示 |
| 确认并匹配 | 307 | 添加重试机制、详细错误展示 |

`frontend/src/pages/Create.tsx:84` 中 `transcribeLyrics` 为 fire-and-forget 调用，失败时用户无感知。

### 稳定性优化

| 功能 | 文件位置 | 说明 |
|------|----------|------|
| **查询改写缓存限制** | `src/services/matching/query_rewriter.py:22` | `_cache` 字典无大小限制和 TTL，长期运行有内存泄漏风险 |
| **数据库连接重试** | `src/infra/persistence/database.py` | 连接失败直接抛 RuntimeError，无重试逻辑 |
| **Redis 限流回退清理** | `src/infra/messaging/redis_pool.py:17` | `_fallback_buckets` 字典在 Redis 不可用时无限增长 |
| **OTEL 端点配置化** | `src/infra/config/settings.py:50` | 硬编码为 `localhost:4317`，应支持环境变量配置 |

### 代码质量

- [ ] **异常上下文保留**：多处 `# noqa: BLE001` 捕获宽泛异常，应添加更具体的错误上下文
- [ ] **前端错误上报**：接入错误监控服务（如 Sentry），替代 console.error

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

### v0.5.0 (2025-12-14)
- 🆕 新增视频比例选择功能：支持 16:9（默认）和 4:3 输出视频
- 🆕 新增双语字幕支持：中英双语字幕，用户可选
- 🆕 新增实时日志查看功能：管理后台支持 SSE 实时日志流
- 🆕 新增节拍分析 API：手动触发分析、获取结果、卡点开关控制
- 🔧 优化视频比例处理：使用模糊背景方式，保持画面完整
- 🔧 优化视频去重逻辑：使用随机选择替代固定 fallback
- 🔧 修复字幕相关问题：扩展名、字体大小、边距优化
- 🔧 改进用户体验：错误提示、状态按钮、名称长度限制

### v0.4.0 (2025-12-13)
- 🆕 新增鼓点自动卡点功能（类似剪映）：基于 librosa onset_detect 检测音频鼓点
- 🆕 新增双模式卡点：`onset` 模式（鼓点对齐）和 `action` 模式（动作点对齐）
- 🆕 新增 5 候选容错机制：每句歌词保留 5 个候选视频，渲染失败时自动回退
- 🔧 修复视频循环播放问题：禁止循环，时长不足的候选直接丢弃
- 🔧 修复 Fallback 视频时间错误：统一从 0 开始裁剪
- 📝 完善渲染日志：候选裁剪失败时记录详细日志并自动尝试下一个

### v0.3.0 (2025-11-30)
- 🆕 新增用户前端 (frontend/)：提供歌曲上传、视频生成、结果查看功能
- 🆕 新增管理后台 (web/)：任务列表、任务详情、资源管理、配置页面
- 🆕 新增管理后台 API：任务管理、资源管理、系统配置接口
- 🆕 新增渲染进度追踪：百分比进度条显示 (0-100%)，实时展示渲染各阶段
- 🆕 新增渲染任务取消功能：支持取消排队中或进行中的渲染任务
- 🔧 优化 mix 状态同步：渲染任务状态变更时自动更新关联 mix 的 render_status
- 📊 前端技术栈：React + TypeScript + Vite + TailwindCSS + TanStack Query

### v0.2.2 (2025-11-23)
- 🆕 新增歌词片段细粒度优化：启用 word_timestamps 生成更多短片段
- 🆕 新增音视频同步修复：裁剪音频到歌词时间范围，解决画面提前问题
- 🔧 修复视频画面比音频提前的同步问题（完美对齐）
- 🎯 字幕时间自动归零（从第一个歌词时间开始计算相对偏移）
- 📊 片段数量提升：从 26 个提升至 49-74 个（视歌曲而定），画面更丰富
- ⚡ 音频裁剪功能：自动裁剪音频只保留歌词部分，跳过前奏和尾奏
- 🎬 视频时长精准匹配：视频、音频、字幕三者完美同步

### v0.2.1 (2025-11-23)
- 🆕 新增 RMS 能量分析自动跳过音乐前奏功能
- 🔧 修复带长前奏歌曲的时间戳偏移问题（78 秒偏移 → 0 秒）
- 🔧 提高 no_speech_prob 阈值至 0.9，保留背景音乐较响的人声片段
- 🎯 支持自动检测 >= 5 秒的前奏并跳过
- 📊 添加 vocal_detection 和 skipping_intro 日志事件

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

**文档版本**: v0.5.0
**最后更新**: 2025-12-14

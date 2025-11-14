# 歌词语义混剪系统

基于 TwelveLabs AI 视频理解能力的智能歌词视频混剪系统，自动将歌词语义与视频片段进行精准匹配，生成高质量的卡点视频。

## 项目简介

本系统是一个异步歌词语义混剪后端服务，主要功能包括：

- 🎵 **智能歌词识别**：使用 Whisper 进行音频转文字
- 🎬 **语义视频匹配**：通过 TwelveLabs 视频理解 API 智能匹配歌词与视频片段
- ⚡ **异步渲染队列**：基于 Redis/ARQ 的高性能异步任务处理
- 📊 **可观测性**：完整的 OpenTelemetry + Prometheus + Loki 监控体系
- 🎯 **精准对齐**：歌词与视频片段的毫秒级时间轴同步

## 核心特性

### 1. Preview Manifest API
- 查看完整的歌词-视频时间线清单
- 每句歌词的视频片段、起止时间与置信度
- 支持 Fallback 标识，方便审核与补片

### 2. 渲染质量监控
- 字幕与画面对齐偏差量化追踪
- 平均/最大延迟等关键指标
- 实时推送到 Prometheus 监控平台

### 3. Fallback 优雅降级
- TwelveLabs 无匹配时自动使用备用视频
- 完整的追踪与告警机制
- 支持人工补片工作流

## 技术栈

- **后端框架**：FastAPI + Uvicorn
- **数据库**：SQLModel + AsyncPG / Aiosqlite
- **任务队列**：Redis + ARQ
- **视频处理**：FFmpeg + Pydub
- **AI 能力**：
  - TwelveLabs - 视频语义理解
  - OpenAI Whisper - 语音识别
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
```

必需的环境变量：
- `TL_API_KEY`: TwelveLabs API 密钥
- `TL_INDEX_ID`: TwelveLabs 视频索引 ID
- `REDIS_URL`: Redis 连接地址
- `FALLBACK_VIDEO_ID`: 备用视频 ID

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

- ✅ Preview Manifest 生成：< 2 秒
- ✅ 平均对齐偏差：≤ 200ms
- ✅ 最大对齐偏差：≤ 400ms
- ✅ Fallback 比例：< 30%

## 贡献指南

欢迎提交 Issue 和 Pull Request！

提交前请确保：
1. 代码通过 Ruff 和 Mypy 检查
2. 添加了相应的测试用例
3. 更新了相关文档

## 许可证

MIT License

## 联系方式

- 项目负责人：twelve_labs
- Email: dev@twelvelabs.local

---

**文档版本**: v0.1.0
**最后更新**: 2025-11-14

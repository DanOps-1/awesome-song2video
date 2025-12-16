# 歌词混剪系统架构文档

**日期**: 2025-12-16
**项目**: 歌词语义混剪 API
**版本**: v2.0

---

## 系统架构概览

```
┌─────────────────┐
│   FastAPI App   │  <- src/api/main.py
│   (HTTP Server) │
└────────┬────────┘
         │
         ├─── API Routes (REST)
         │    ├── /api/v1/mixes                     (创建/查询 mix)
         │    ├── /api/v1/mixes/{id}/fetch-lyrics   (在线歌词获取)
         │    ├── /api/v1/mixes/{id}/transcribe     (Whisper 识别)
         │    ├── /api/v1/mixes/{id}/import-lyrics  (手动导入歌词)
         │    ├── /api/v1/mixes/{id}/lines          (歌词行管理)
         │    ├── /api/v1/mixes/{id}/preview        (预览)
         │    ├── /api/v1/mixes/{id}/render         (渲染)
         │    ├── /api/v1/mixes/{id}/analyze-beats  (节拍分析)
         │    ├── /api/v1/mixes/{id}/beats          (获取节拍数据)
         │    ├── /api/v1/mixes/{id}/beat-sync      (开关节拍同步)
         │    ├── /api/v1/render/config             (渲染配置热加载)
         │    └── /api/v1/admin/*                   (管理后台)
         │
         ├─── Background Workers (ARQ)
         │    ├── timeline_worker    (歌词时间线生成)
         │    └── render_worker      (视频渲染)
         │
         └─── External Services
              ├── TwelveLabs API    (视频搜索)
              ├── DeepSeek API      (查询改写)
              ├── PostgreSQL/SQLite (数据存储)
              └── Redis             (任务队列 + 配置热加载)
```

---

## 核心模块

### 1. 歌词获取 (src/lyrics/)

**LyricsFetcher** - 多源歌词获取器

```python
# 支持多平台自动降级
sources = [
    "QQ Music",       # 覆盖最全（包括周杰伦）
    "NetEase Music",  # 网易云
    "Kugou Music",    # 酷狗
    "LRCLIB",         # 国际歌曲
]
```

**关键文件**:
- `src/lyrics/fetcher.py` - 主入口
- `src/lyrics/sources/` - 各平台适配器

### 2. 时间线构建 (src/pipelines/matching/)

**TimelineBuilder** - 视频匹配核心

```
歌词文本 → Whisper 转录 → 分句处理 → TwelveLabs 搜索 → 候选排序 → 去重优化
```

**关键文件**:
- `src/pipelines/matching/timeline_builder.py` - 主逻辑
- `src/services/matching/twelvelabs_client.py` - TwelveLabs API 封装
- `src/services/matching/query_rewriter.py` - DeepSeek 查询改写

### 3. 时间线编辑 (src/pipelines/editing/)

**TimelineEditor** - 歌词行编辑器

```python
# 支持操作
- list_lines()           # 列出所有歌词行
- get_line()             # 获取单行详情
- lock_line()            # 锁定选中片段
- rerun_search()         # 重新搜索候选
```

**关键文件**:
- `src/pipelines/editing/timeline_editor.py` - 编辑器实现

### 4. 节拍分析 (src/audio/)

**BeatDetector** - 音频节拍检测

```python
# 使用 librosa 进行节拍分析
result = {
    "bpm": 120.5,
    "beat_times": [0.5, 1.0, 1.5, ...],  # 节拍时间点
    "downbeats": [0.5, 2.5, 4.5, ...],    # 重拍时间点
    "tempo_stability": 0.95,              # 速度稳定性
}
```

**OnsetDetector** - 鼓点检测（类似剪映）

```python
# 检测音频中的打击乐 onset
onset_times = [0.1, 0.6, 1.1, ...]  # 鼓点时间
```

**BeatAligner** - 视频片段与节拍对齐

```python
# 两种对齐模式
BEAT_SYNC_MODE=onset   # 鼓点对齐（默认，类似剪映）
BEAT_SYNC_MODE=action  # 视觉动作点对齐
```

**关键文件**:
- `src/audio/beat_detector.py` - 节拍检测
- `src/audio/onset_detector.py` - 鼓点检测
- `src/services/matching/beat_aligner.py` - 对齐服务

### 5. 视频检索 (src/retrieval/)

**工厂模式支持多种检索器**:

```python
from src.retrieval import create_retriever

# 当前实现
retriever = create_retriever("twelvelabs")  # TwelveLabs API (默认)
retriever = create_retriever("clip")        # CLIP 本地检索 (备用)
retriever = create_retriever("vlm")         # VLM 检索 (备用)
```

**关键文件**:
- `src/retrieval/protocol.py` - 检索协议定义
- `src/retrieval/factory.py` - 检索器工厂
- `src/retrieval/twelvelabs/retriever.py` - TwelveLabs 实现

### 6. 视频渲染 (src/workers/)

**RenderWorker** - 并行视频渲染

```
候选片段 → 并行下载裁剪 → 拼接 → 合成音轨 → 字幕烧录 → 输出
```

**特性**:
- 并行裁剪（默认 4 并发）
- 配置热加载（Redis Pub/Sub）
- 占位片段回退
- 视频比例控制

**关键文件**:
- `src/workers/render_worker.py` - 渲染 Worker
- `src/workers/timeline_worker.py` - 时间线 Worker

### 7. 管理后台 (src/api/v1/routes/admin/)

**Admin API**:
- `/api/v1/admin/tasks` - 任务管理
- `/api/v1/admin/logs` - 日志查看器
- `/api/v1/admin/status` - 系统状态

**日志流 API**:
```python
# 查询日志
GET /api/v1/admin/logs?level=ERROR&limit=100

# 流式日志（SSE）
GET /api/v1/admin/logs/stream

# 日志文件列表
GET /api/v1/admin/logs/files
```

---

## TwelveLabs SDK 调用流程

### 1. 自动生成时间线

```
POST /api/v1/mixes → create_mix()
                        │
                        ├── 推送任务到 Redis
                        │
                        ▼
              timeline_worker.build_timeline()
                        │
                        ├── Whisper 转录（如需）
                        │
                        ├── 歌词分句
                        │
                        └── 为每句搜索视频
                                │
                                ├── TwelveLabsClient.search_segments()
                                │
                                └── 分数低于阈值? → QueryRewriter.rewrite()
```

### 2. 手动重新搜索

```
POST /api/v1/mixes/{id}/lines/{line_id}/search
                        │
                        ▼
              TimelineEditor.rerun_search()
                        │
                        └── TwelveLabsClient.search_segments()
```

---

## TwelveLabsClient 详解

**文件**: `src/services/matching/twelvelabs_client.py`

### 关键配置

```bash
# .env
TL_API_KEY=tlk_xxx                    # API Key
TL_INDEX_ID=6911aaadd68fb776bc1bd8e7  # Index ID
TL_LIVE_ENABLED=true                  # true=真实API, false=Mock

# 搜索模态
TL_AUDIO_SEARCH_ENABLED=false         # 是否启用音频搜索
```

### 搜索方法

```python
async def search_segments(self, query: str, limit: int = 5):
    """
    搜索视频片段

    - 支持 Mock 模式（开发测试）
    - 多选项重试策略
    - 结果标准化
    """
    if not self._live_enabled:
        return self._mock_results(query, limit)

    # 调用 TwelveLabs SDK
    pager = self._client.search.query(
        index_id=self._index_id,
        query_text=query,
        search_options=["visual"],
        group_by="clip",
        page_limit=limit,
    )

    return self._convert_results(pager, limit)
```

### 返回格式

```python
[
    {
        "id": "uuid",
        "video_id": "6911acda8bf751b791733149",
        "start": 89333,  # 毫秒
        "end": 96233,
        "score": 0.71
    },
    ...
]
```

---

## 渲染流程

### 1. 用户锁定歌词行

```
PATCH /api/v1/mixes/{mix_id}/lines/{line_id}
{
  "selected_segment_id": "match-id-123"
}
```

### 2. 提交渲染任务

```
POST /api/v1/mixes/{mix_id}/render
{
  "resolution": "1080p",
  "frame_rate": 25,
  "aspect_ratio": "16:9"  # 支持 16:9, 9:16, 1:1
}
```

### 3. Render Worker 处理

```python
async def render_mix(ctx, job_id: str):
    # 1. 获取锁定的歌词行
    lines = await song_repo.list_locked_lines(mix_request_id)

    # 2. 并行裁剪视频片段
    scheduler = RenderClipScheduler(max_parallelism=4)
    clips = await scheduler.run(tasks)

    # 3. FFmpeg 拼接
    await ffmpeg_concat(clips, output_path)

    # 4. 合成音轨
    await ffmpeg_merge_audio(output_path, audio_path)

    # 5. 烧录字幕（可选）
    await ffmpeg_burn_subtitles(output_path, srt_path)
```

---

## 数据库模型

### SongMixRequest (Mix 任务)
```python
{
    "id": "uuid",
    "song_title": "歌曲名",
    "artist": "歌手",
    "source_type": "upload|search",
    "audio_asset_id": "音频路径",
    "language": "zh|en|ja",
    "timeline_status": "pending|processing|generated|failed",
    "render_status": "idle|queued|rendering|completed|failed",
    "metrics": {...}
}
```

### LyricLine (歌词行)
```python
{
    "id": "uuid",
    "mix_request_id": "mix_uuid",
    "line_no": 1,
    "original_text": "歌词内容",
    "start_time_ms": 0,
    "end_time_ms": 3000,
    "status": "pending|locked",
    "selected_segment_id": "match_uuid",
    "auto_confidence": 0.85
}
```

### VideoSegmentMatch (候选片段)
```python
{
    "id": "uuid",
    "line_id": "line_uuid",
    "source_video_id": "6911acda8bf751b791733149",
    "start_time_ms": 89333,
    "end_time_ms": 96233,
    "score": 0.71,
    "generated_by": "auto|twelvelabs_api|manual"
}
```

### RenderJob (渲染任务)
```python
{
    "id": "uuid",
    "mix_request_id": "mix_uuid",
    "job_status": "queued|running|success|failed",
    "output_asset_id": "path/to/video.mp4",
    "metrics": {"render": {...}}
}
```

### BeatAnalysisData (节拍分析)
```python
{
    "id": "uuid",
    "mix_request_id": "mix_uuid",
    "bpm": 120.5,
    "beat_times": [0.5, 1.0, 1.5, ...],
    "downbeats": [0.5, 2.5, 4.5, ...],
    "tempo_stability": 0.95
}
```

---

## 关键配置

### 环境变量 (`.env`)

```bash
# TwelveLabs 配置
TL_API_KEY=tlk_xxx
TL_INDEX_ID=6911aaadd68fb776bc1bd8e7
TL_LIVE_ENABLED=true

# DeepSeek 查询改写
DEEPSEEK_API_KEY=sk-xxxxx
QUERY_REWRITE_ENABLED=true
QUERY_REWRITE_SCORE_THRESHOLD=1.0  # 分数阈值
QUERY_REWRITE_MAX_ATTEMPTS=3

# Whisper 音频识别
WHISPER_MODEL_NAME=large-v3

# 节拍同步
BEAT_SYNC_ENABLED=true
BEAT_SYNC_MODE=onset  # onset|action
BEAT_SYNC_MAX_ADJUSTMENT_MS=500
BEAT_SYNC_ONSET_TOLERANCE_MS=80

# 视频过滤（跳过片头片尾）
VIDEO_INTRO_SKIP_MS=8000
VIDEO_OUTRO_SKIP_MS=5000

# 数据库
POSTGRES_DSN=sqlite+aiosqlite:///./data/db/dev.db

# Redis (任务队列)
REDIS_URL=redis://localhost:6379

# Fallback 视频
FALLBACK_VIDEO_ID=6911acda8bf751b791733149
```

---

## 运行服务

### 方式 1: 启动完整服务

```bash
# 使用启动脚本
bash start.sh

# 或手动启动
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload &
python -m src.workers.timeline_worker &
python -m src.workers.render_worker &
```

### 方式 2: API 测试

```bash
# 创建 mix
curl -X POST http://localhost:8000/api/v1/mixes \
  -H "Content-Type: application/json" \
  -d '{
    "song_title": "测试",
    "artist": "歌手",
    "audio_asset_id": "test.mp3"
  }'

# 获取歌词（在线）
curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/fetch-lyrics

# 或 Whisper 识别
curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/transcribe

# 查询歌词行
curl http://localhost:8000/api/v1/mixes/{mix_id}/lines

# 提交渲染
curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/render
```

### 方式 3: 直接调用代码

```python
import asyncio
from src.services.matching.twelvelabs_client import client

async def test():
    results = await client.search_segments("树木丛生", limit=3)
    for r in results:
        print(f"video_id: {r['video_id']}, score: {r['score']}")

asyncio.run(test())
```

---

## 总结

### 核心调用链

1. **歌词获取**: LyricsFetcher → QQ/NetEase/Kugou/LRCLIB
2. **时间线生成**: TimelineBuilder → TwelveLabsClient → QueryRewriter
3. **时间线编辑**: TimelineEditor → TwelveLabsClient
4. **节拍同步**: BeatDetector/OnsetDetector → BeatAligner
5. **视频渲染**: RenderWorker → FFmpeg

### 生产代码特点

- 支持 Mock 模式，方便开发测试
- 分数阈值触发智能改写
- 节拍对齐提升视频节奏感
- 并行裁剪提升渲染效率
- 配置热加载无需重启
- 结构化日志便于排查

---

**文档生成人**: Claude Code
**最后更新**: 2025-12-16

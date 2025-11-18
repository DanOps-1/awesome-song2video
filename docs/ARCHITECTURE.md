# 歌词混剪系统架构文档

**日期**: 2025-11-13
**项目**: 歌词语义混剪 API

---

## 系统架构概览

```
┌─────────────────┐
│   FastAPI App   │  <- src/api/main.py
│   (HTTP Server) │
└────────┬────────┘
         │
         ├─── API Routes (REST)
         │    ├── /api/v1/mixes                (创建/查询 mix)
         │    ├── /api/v1/mixes/{id}/lines     (歌词行管理)
         │    ├── /api/v1/mixes/{id}/preview   (预览)
         │    └── /api/v1/mixes/{id}/render    (渲染)
         │
         ├─── Background Workers (Arq)
         │    ├── timeline_worker    (生成歌词时间线)
         │    └── render_worker      (渲染视频)
         │
         └─── External Services
              ├── TwelveLabs API    (视频搜索)
              ├── PostgreSQL/SQLite (数据存储)
              └── Redis             (任务队列)
```

---

## TwelveLabs SDK 调用流程

### 1️⃣ 入口：FastAPI App

**文件**: `src/api/main.py`

```python
app = FastAPI(title="歌词语义混剪 API")
app.include_router(mixes.router)        # 创建 mix
app.include_router(mix_lines.router)    # 管理歌词行
app.include_router(preview.router)      # 预览
app.include_router(render.router)       # 渲染
```

**启动命令**:
```bash
uvicorn src.api.main:app --reload
```

---

### 2️⃣ 调用路径 A：自动生成时间线

#### 用户请求
```
POST /api/v1/mixes
{
  "song_title": "测试歌曲",
  "lyrics_text": "东临碣石，以观沧海...",
  "audio_asset_id": "audio.mp3"
}
```

#### 后端处理流程

**Step 1**: API 接收请求 (`src/api/v1/routes/mixes.py`)
```python
@router.post("")
async def create_mix(body: CreateMixRequest):
    mix = SongMixRequest(...)
    await repo.create_request(mix)

    # 提交到后台任务队列
    await queue.enqueue_job("build_timeline", mix.id)
    return mix
```

**Step 2**: Timeline Worker 处理 (`src/workers/timeline_worker.py`)
```python
async def build_timeline(ctx, mix_id: str):
    mix = await repo.get_request(mix_id)

    # 调用 TimelineBuilder
    result = await builder.build(
        audio_path=audio_path,
        lyrics_text=mix.lyrics_text
    )

    # 保存歌词行和候选片段
    await repo.bulk_insert_lines(lines)
    await repo.attach_candidates(candidates)
    await repo.update_timeline_status(mix_id, "generated")
```

**Step 3**: TimelineBuilder 调用搜索 (`src/pipelines/matching/timeline_builder.py`)
```python
class TimelineBuilder:
    async def build(self, audio_path, lyrics_text):
        # 解析歌词，提取时间轴
        lines = self._parse_lyrics(lyrics_text)

        # 为每行歌词搜索视频片段
        for line in lines:
            # ⭐ 这里调用 TwelveLabs
            candidates = await client.search_segments(
                line.text,
                limit=5
            )
            line.candidates = candidates

        return result
```

**Step 4**: TwelveLabsClient 执行搜索 (`src/services/matching/twelvelabs_client.py`)
```python
class TwelveLabsClient:
    async def search_segments(self, query: str, limit: int = 5):
        # ⭐⭐⭐ 真正调用 TwelveLabs SDK 的地方！
        option_chain = (
            [["visual", "audio"], ["audio"], ["visual"]]
            if self._audio_enabled
            else [["visual"]]  # 默认仅视觉匹配
        )
        # 实际实现中会按 option_chain 轮询
        pager = self._client.search.query(
            index_id=self._index_id,
            query_text=query,
            search_options=option_chain[0],
            group_by="clip",
            page_limit=max(limit, 10),
        )

        # 转换为标准格式
        return self._convert_results(pager, limit)
```

---

### 3️⃣ 调用路径 B：手动重新搜索

#### 用户请求
```
POST /api/v1/mixes/{mix_id}/lines/{line_id}/search
{
  "prompt_override": "森林树木"
}
```

#### 后端处理流程

**Step 1**: API 接收请求 (`src/api/v1/routes/mix_lines.py`)
```python
@router.post("/{line_id}/search")
async def search_new_segments(mix_id, line_id, body):
    # 调用 TimelineEditor
    candidates = await editor.rerun_search(
        line_id,
        prompt_override=body.prompt_override
    )
    return {"candidates": candidates}
```

**Step 2**: TimelineEditor 调用搜索 (`src/services/timeline_editor.py`)
```python
class TimelineEditor:
    async def rerun_search(self, line_id, prompt_override=None):
        line = await timeline_repo.get_line(line_id)
        query = prompt_override or line.original_text

        # ⭐ 直接调用 TwelveLabs
        results = await client.search_segments(query, limit=5)

        # 保存新候选片段
        await repo.replace_candidates(line_id, candidates)
        return serialized
```

**Step 3**: TwelveLabsClient 执行搜索（同上）

---

## TwelveLabsClient 详解

### 核心代码位置

**文件**: `src/services/matching/twelvelabs_client.py`

### 关键方法

#### 1. `__init__()` - 初始化客户端

```python
def __init__(self):
    self._settings = get_settings()
    self._live_enabled = self._settings.tl_live_enabled  # 控制真实/Mock
    self._index_id = self._settings.tl_index_id
    self._client = None

    if self._live_enabled:
        self._advance_client()  # 初始化 TwelveLabs SDK
```

**配置来源**: `.env` 文件
```bash
TL_API_KEY=tlk_xxx
TL_INDEX_ID=6911aaadd68fb776bc1bd8e7
TL_LIVE_ENABLED=true
TL_AUDIO_SEARCH_ENABLED=false
```

#### 2. `search_segments()` - 搜索视频片段

```python
async def search_segments(self, query: str, limit: int = 5):
    # Mock 模式
    if not self._live_enabled:
        return self._mock_results(query, limit)

    # 多选项重试策略（默认仅视觉，配置开启时再加入音频）
    option_chain = (
        [["visual", "audio"], ["audio"], ["visual"]]
        if self._audio_enabled
        else [["visual"]]
    )

    for options in option_chain:
        try:
            # ⭐ 调用 TwelveLabs SDK
            pager = self._client.search.query(
                index_id=self._index_id,
                query_text=query,
                search_options=options,
                group_by="clip",
                page_limit=max(limit, 10),
            )

            results = self._convert_results(pager, limit)
            if results:
                return results  # 找到结果，返回
        except Exception:
            # 失败则尝试下一个选项
            continue

    return []  # 所有选项都失败
```

#### 3. `_convert_results()` - 转换结果格式

```python
def _convert_results(self, items, limit):
    results = []
    for item in items:
        clips = getattr(item, "clips", None) or []

        if clips:
            # 有 clips，遍历每个 clip
            for clip in clips:
                results.append(
                    self._build_candidate_dict(
                        clip.video_id or item.video_id,
                        clip.start,
                        clip.end,
                        clip.score
                    )
                )
        else:
            # 没有 clips，用 item 本身
            results.append(
                self._build_candidate_dict(
                    item.video_id,
                    item.start,
                    item.end,
                    item.score
                )
            )

        if len(results) >= limit:
            break

    return results
```

**返回格式**:
```python
[
    {
        "id": "uuid",
        "video_id": "6911acda8bf751b791733149",
        "start": 89333,  # 毫秒
        "end": 96233,
        "score": 71.07
    },
    ...
]
```

---

## 渲染流程

### 1️⃣ 用户锁定歌词行

```
PATCH /api/v1/mixes/{mix_id}/lines/{line_id}
{
  "selected_segment_id": "match-id-123"
}
```

### 2️⃣ 提交渲染任务

```
POST /api/v1/mixes/{mix_id}/render
{
  "resolution": "1080p",
  "frame_rate": 25
}
```

### 3️⃣ Render Worker 处理

**文件**: `src/workers/render_worker.py`

```python
async def render_mix(ctx, job_id: str):
    job = await repo.get(job_id)
    mix = await song_repo.get_request(job.mix_request_id)

    # ⭐ 只渲染 status='locked' 的歌词行
    lines = await song_repo.list_locked_lines(job.mix_request_id)

    # 使用 FFmpeg 渲染
    render_lines = [_build_render_line(line) for line in lines]
    # ... FFmpeg 处理 ...

    # 保存结果
    await repo.mark_success(
        job_id,
        output_asset_id=output_path,
        metrics={"render": render_metrics}
    )
```

---

## 数据库模型

### SongMixRequest (Mix 任务)
```python
{
    "id": "uuid",
    "song_title": "歌曲名",
    "lyrics_text": "歌词内容",
    "audio_asset_id": "音频路径",
    "timeline_status": "pending|generating|generated|failed",
    "render_status": "idle|queued|rendering|completed|failed",
    "metrics": {
        "preview": {...},
        "render": {...}
    }
}
```

### LyricLine (歌词行)
```python
{
    "id": "uuid",
    "mix_request_id": "mix_uuid",
    "line_no": 1,
    "original_text": "东临碣石，以观沧海",
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
    "index_id": "tl_index_id",
    "start_time_ms": 89333,
    "end_time_ms": 96233,
    "score": 71.07,
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
    "metrics": {
        "render": {
            "line_count": 3,
            "avg_delta_ms": 500,
            "queued_at": "2025-11-13T12:00:00Z",
            "finished_at": "2025-11-13T12:00:05Z"
        }
    }
}
```

---

## 运行生产代码

### 方式 1: 启动 API 服务器

```bash
# 1. 启动 FastAPI
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 2. 启动 Timeline Worker (处理搜索任务)
arq src.workers.timeline_worker.WorkerSettings

# 3. 启动 Render Worker (处理渲染任务)
arq src.workers.render_worker.WorkerSettings
```

### 方式 2: 使用 API 测试

```bash
# 创建 mix
curl -X POST http://localhost:8000/api/v1/mixes \
  -H "Content-Type: application/json" \
  -d '{
    "song_title": "测试",
    "lyrics_text": "树木丛生，百草丰茂",
    "audio_asset_id": "test.mp3"
  }'

# 等待 timeline_worker 处理完成

# 查询歌词行和候选片段
curl http://localhost:8000/api/v1/mixes/{mix_id}/lines

# 锁定歌词行
curl -X PATCH http://localhost:8000/api/v1/mixes/{mix_id}/lines/{line_id} \
  -H "Content-Type: application/json" \
  -d '{"selected_segment_id": "match-id"}'

# 提交渲染
curl -X POST http://localhost:8000/api/v1/mixes/{mix_id}/render
```

### 方式 3: 直接调用代码 (测试)

创建测试脚本 `test_production_code.py`:

```python
import asyncio
from src.services.matching.twelvelabs_client import client

async def test():
    # 直接调用生产代码的搜索
    results = await client.search_segments("树木丛生", limit=3)

    for i, result in enumerate(results, 1):
        print(f"结果 {i}:")
        print(f"  video_id: {result['video_id']}")
        print(f"  时间: {result['start']}ms - {result['end']}ms")
        print(f"  得分: {result['score']}")

asyncio.run(test())
```

运行:
```bash
python test_production_code.py
```

---

## 关键配置

### 环境变量 (`.env`)

```bash
# TwelveLabs 配置
TL_API_KEY=tlk_xxx                      # API Key
TL_INDEX_ID=6911aaadd68fb776bc1bd8e7   # Index ID
TL_LIVE_ENABLED=true                    # true=真实API, false=Mock

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./dev.db

# Redis (任务队列)
REDIS_URL=redis://localhost:6379

# Fallback 视频
FALLBACK_VIDEO_ID=6911acda8bf751b791733149
```

---

## Mock vs 真实 API

### Mock 模式 (`TL_LIVE_ENABLED=false`)

```python
# 返回假数据，用于本地开发
def _mock_results(self, query, limit):
    matches = []
    for idx in range(limit):
        start = idx * 2000
        matches.append({
            "id": str(uuid4()),
            "video_id": "fallback_video_id",
            "start": start,
            "end": start + 1500,
            "score": random.uniform(0.6, 0.95),
        })
    return matches
```

### 真实 API 模式 (`TL_LIVE_ENABLED=true`)

```python
# 调用真实的 TwelveLabs SDK
pager = self._client.search.query(
    index_id=self._index_id,
    query_text=query,
    search_options=["visual"],  # 默认仅视觉；设置 TL_AUDIO_SEARCH_ENABLED=true 才会附加 audio
    group_by="clip",
    page_limit=10,
)
```

---

## 总结

### ✅ TwelveLabs SDK 调用位置

**唯一入口**: `src/services/matching/twelvelabs_client.py`
- 方法: `TwelveLabsClient.search_segments()`
- 行号: 63-69

### ✅ 两个调用场景

1. **自动搜索** (Timeline Worker)
   - 创建 mix 时自动触发
   - 为所有歌词行搜索候选片段

2. **手动搜索** (Timeline Editor)
   - 用户手动触发
   - 为单个歌词行重新搜索

### ✅ 生产代码特点

- ✅ 支持 Mock 模式，方便开发测试
- ✅ 默认仅视觉匹配，可配置开启 visual+audio → audio → visual 的重试链路
- ✅ 优雅降级（有 clips 用 clips，没有用 item）
- ✅ 速率限制和故障转移
- ✅ 结构化日志记录

### ✅ 如何运行

```bash
# 启动完整服务
uvicorn src.api.main:app --reload &
arq src.workers.timeline_worker.WorkerSettings &
arq src.workers.render_worker.WorkerSettings &

# 或直接调用
python test_production_code.py
```

---

**文档生成人**: Claude Code (Sonnet 4.5)
**最后更新**: 2025-11-13

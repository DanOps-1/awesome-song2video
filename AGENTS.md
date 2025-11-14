# twelve_labs Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-11

## Active Technologies

- Python 3.11 + asyncio（uvloop）
- FastAPI + httpx
- TwelveLabs Python SDK（文本索引与视频语义匹配）
- SQLModel + asyncpg（PostgreSQL 15）
- Redis 7 + Arq worker（匹配/渲染队列）
- FFmpeg CLI + ASS 字幕模板
- Whisper large-v3 + Pydub（歌词时间戳）
- OpenTelemetry（Prometheus / Loki 输出）

## Project Structure

```text
src/
├── api/v1/
├── domain/
│   ├── models/
│   └── services/
├── pipelines/
│   ├── lyrics_ingest/
│   ├── matching/
│   └── rendering/
├── infra/
│   ├── persistence/
│   ├── messaging/
│   └── observability/
└── workers/
    ├── timeline_worker.py
    └── render_worker.py

tests/
├── unit/
├── contract/
├── integration/
└── golden/
```

## Commands

- `uvicorn src.api.main:app --reload --port 8080`：本地 API。
- `arq src.workers.timeline_worker.WorkerSettings`：歌词/匹配 worker。
- `arq src.workers.render_worker.WorkerSettings`：渲染/FFmpeg worker。
- `pytest && ruff check && mypy`：CI 质量基线。
- `scripts/dev/seed_demo.sh`：创建演示歌曲与媒资。

## Code Style

- 强制类型标注（mypy --strict），Domain 层使用 SQLModel。
- 模块/类命名使用中文语义对应的英文全拼，不可使用单字母。
- 日志使用结构化 JSON，字段名采用蛇形并包含 `trace_id`。
- 所有注释、文档、提交信息均使用简体中文，首次出现的英文术语需附中文解释。

## Recent Changes

- 001-lyrics-video-sync：新增歌词语义混剪方案，确定技术栈与模块划分。

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->

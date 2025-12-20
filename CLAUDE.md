# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 重要：使用 uv 环境

**所有 Python 命令必须使用 `uv run` 前缀运行**，确保使用项目的虚拟环境：

```bash
# 正确 ✅
uv run python -m pytest tests/
uv run ruff check src tests
uv run mypy src

# 错误 ❌
python -m pytest tests/
ruff check src tests
mypy src
```

## Project Overview

This is an async lyrics-video mashup backend system that uses TwelveLabs AI for semantic video understanding. It automatically matches lyrics with video clips to generate karaoke-style videos.

## Common Commands

### Development
```bash
# Start all services (backend + frontends)
bash start.sh

# Start backend API only (port 8000)
uv run python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Start workers
uv run python -m src.workers.render_worker    # Video rendering worker
uv run python -m src.workers.timeline_worker  # Timeline generation worker

# Start frontends
cd apps/frontend && npm run dev -- --port 6008  # User frontend
cd apps/web && npm run dev -- --port 6006       # Admin dashboard
```

### Testing
```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/contract/test_health.py

# Run e2e tests
uv run python scripts/dev/e2e_full_render_test.py

# Test lyrics fetcher
uv run python -m src.lyrics.fetcher "歌曲名" "歌手名"
```

### Code Quality
```bash
# Lint and format
uv run ruff check src tests
uv run ruff format src tests

# Type checking
uv run mypy src
```

### Pre-commit Checks (IMPORTANT)
**每次提交代码前，必须在本地运行以下检查确保 CI 能通过：**

```bash
# 1. Python 代码检查（必须通过）
uv run ruff check src tests && uv run ruff format --check src tests

# 2. 前端构建检查（必须通过）
cd apps/frontend && npx vite build

# 3. 管理后台构建检查（必须通过）
cd apps/web && npx vite build
```

或者一键运行所有检查：
```bash
uv run ruff check src tests && uv run ruff format --check src tests && \
  (cd apps/frontend && npx vite build) && \
  (cd apps/web && npx vite build) && \
  echo "✅ All checks passed!"
```

如果格式检查失败，运行 `uv run ruff format src tests` 自动修复。

### Prerequisites
- Python >= 3.11
- Redis (must be running)
- FFmpeg
- Node.js >= 18 (for frontends)

## Architecture

### Core Data Flow
1. **Audio Upload** → User uploads audio file
2. **Lyrics Acquisition** → Multi-source lyrics search (recommended) or Whisper ASR (fallback)
3. **Lyrics Confirmation** → User reviews/edits lyrics
4. **Video Matching** → TwelveLabs API matches each lyric line to video segments
5. **Rendering** → FFmpeg concatenates clips with audio and burned-in subtitles

### Lyrics Acquisition (Multi-Source)
The system supports two lyrics acquisition modes:
1. **Online Search (Recommended)**: Fetches lyrics from multiple platforms with auto-fallback
   - QQ Music (best coverage, including Jay Chou)
   - NetEase Cloud Music
   - Kugou Music
   - LRCLIB (international songs)
2. **AI Recognition**: Uses Whisper ASR for rare songs or original content

### Two-Phase Timeline Generation
The system uses a two-phase workflow in `timeline_worker.py`:
1. `transcribe_lyrics`: Whisper recognition only (pending → transcribing → transcribed)
2. `match_videos`: Video matching for confirmed lyrics (transcribed → matching → generated)

### Key Services
- **LyricsFetcher** (`src/lyrics/fetcher.py`): Multi-source lyrics fetcher with auto-fallback (QQ/NetEase/Kugou/LRCLIB)
- **TimelineBuilder** (`src/pipelines/matching/timeline_builder.py`): Orchestrates Whisper transcription and TwelveLabs video search with query rewriting and deduplication
- **RenderWorker** (`src/workers/render_worker.py`): Parallel clip extraction with FFmpeg, supports hot-reload config via Redis, video aspect ratio, bilingual subtitles
- **QueryRewriter** (`src/services/matching/query_rewriter.py`): Uses DeepSeek LLM to convert abstract lyrics to visual descriptions
- **BeatAligner** (`src/services/matching/beat_aligner.py`): Aligns video clips with music beats/onsets for rhythm sync
- **BeatDetector** (`src/audio/beat_detector.py`): Librosa-based beat detection with BPM, downbeats, tempo stability analysis
- **OnsetDetector** (`src/audio/onset_detector.py`): Detects drum beats from audio for auto-sync (like 剪映)

### API Structure
- `/api/v1/mixes` - Create/manage mix requests
- `/api/v1/mixes/{id}/fetch-lyrics` - Fetch lyrics from online sources (QQ/NetEase/Kugou/LRCLIB)
- `/api/v1/mixes/{id}/transcribe` - Transcribe lyrics using Whisper ASR
- `/api/v1/mixes/{id}/import-lyrics` - Import user-provided lyrics
- `/api/v1/mixes/{id}/lines` - Manage lyric lines
- `/api/v1/mixes/{id}/preview` - Get timeline manifest
- `/api/v1/mixes/{id}/render` - Submit render job
- `/api/v1/mixes/{id}/analyze-beats` - Trigger beat analysis
- `/api/v1/mixes/{id}/beats` - Get beat analysis data
- `/api/v1/mixes/{id}/beat-sync` - Toggle beat sync on/off
- `/api/v1/render/config` - Hot-reload render settings
- `/api/v1/admin/*` - Admin dashboard endpoints
- `/api/v1/admin/logs` - Log viewer API (query, stream, list files)

### Database Models
- `SongMixRequest` - Main mix request entity
- `LyricLine` - Individual lyric lines with timestamps
- `VideoSegmentMatch` - Video candidates for each line
- `RenderJob` - Async render task tracking
- `BeatAnalysisData` - Beat analysis results (BPM, beat times, downbeats, tempo stability)
- `VideoActionCache` - Cached video action points for beat alignment

### Workers (ARQ-based)
Workers use Redis + ARQ for async task processing:
- `timeline_worker`: Handles transcription and video matching
- `render_worker`: Handles video clip extraction and final rendering

## Environment Variables

Required:
- `TL_API_KEY` - TwelveLabs API key
- `TL_INDEX_ID` - TwelveLabs video index ID
- `REDIS_URL` - Redis connection URL
- `POSTGRES_DSN` - Database connection string

Optional AI features:
- `DEEPSEEK_API_KEY` - For query rewriting (improves match rate)
- `QUERY_REWRITE_SCORE_THRESHOLD` - Score threshold for triggering rewrite (default: 0.9, rewrite only when score < threshold)
- `QUERY_REWRITE_MAX_ATTEMPTS` - Max rewrite attempts (default: 3)
- `WHISPER_MODEL_NAME` - Whisper model (default: large-v3)

Beat sync (rhythm alignment):
- `BEAT_SYNC_ENABLED` - Enable beat/onset sync (default: true)
- `BEAT_SYNC_MODE` - `onset` (drum beat alignment, like 剪映) or `action` (visual action points)
- `BEAT_SYNC_MAX_ADJUSTMENT_MS` - Max time offset for alignment (default: 500)
- `BEAT_SYNC_ONSET_TOLERANCE_MS` - Tolerance for onset matching (default: 80)

Video filtering (intro/outro skip):
- `VIDEO_INTRO_SKIP_MS` - Skip video intro in milliseconds (default: 8000, filters title screens)
- `VIDEO_OUTRO_SKIP_MS` - Skip video outro in milliseconds (default: 5000, config defined, filter logic pending)

## Code Conventions

- Use `structlog` for structured logging with event names like `module.action`
- Async-first: All DB operations and external API calls are async
- Settings via `pydantic-settings` in `src/infra/config/settings.py`
- SQLModel for database models with async SQLAlchemy

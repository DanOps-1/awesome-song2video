# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an async lyrics-video mashup backend system that uses TwelveLabs AI for semantic video understanding. It automatically matches lyrics with video clips to generate karaoke-style videos.

## Common Commands

### Development
```bash
# Start all services (backend + frontends)
bash start.sh

# Start backend API only (port 8000)
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Start workers
python -m src.workers.render_worker    # Video rendering worker
python -m src.workers.timeline_worker  # Timeline generation worker

# Start frontends
cd frontend && npm run dev -- --port 6008  # User frontend
cd web && npm run dev -- --port 6006       # Admin dashboard
```

### Testing
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/contract/test_health.py

# Run e2e tests
python scripts/dev/e2e_full_render_test.py

# Test lyrics fetcher
python -m src.lyrics.fetcher "歌曲名" "歌手名"
```

### Code Quality
```bash
# Lint and format
ruff check src tests
ruff format src tests

# Type checking
mypy src
```

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
- **RenderWorker** (`src/workers/render_worker.py`): Parallel clip extraction with FFmpeg, supports hot-reload config via Redis
- **QueryRewriter** (`src/services/matching/query_rewriter.py`): Uses DeepSeek LLM to convert abstract lyrics to visual descriptions

### API Structure
- `/api/v1/mixes` - Create/manage mix requests
- `/api/v1/mixes/{id}/fetch-lyrics` - Fetch lyrics from online sources (QQ/NetEase/Kugou/LRCLIB)
- `/api/v1/mixes/{id}/transcribe` - Transcribe lyrics using Whisper ASR
- `/api/v1/mixes/{id}/import-lyrics` - Import user-provided lyrics
- `/api/v1/mixes/{id}/lines` - Manage lyric lines
- `/api/v1/mixes/{id}/preview` - Get timeline manifest
- `/api/v1/mixes/{id}/render` - Submit render job
- `/api/v1/render/config` - Hot-reload render settings
- `/api/v1/admin/*` - Admin dashboard endpoints

### Database Models
- `SongMixRequest` - Main mix request entity
- `LyricLine` - Individual lyric lines with timestamps
- `VideoSegmentMatch` - Video candidates for each line
- `RenderJob` - Async render task tracking

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
- `QUERY_REWRITE_MANDATORY` - Force rewrite on first query (default: false)
- `WHISPER_MODEL_NAME` - Whisper model (default: large-v3)

## Code Conventions

- Use `structlog` for structured logging with event names like `module.action`
- Async-first: All DB operations and external API calls are async
- Settings via `pydantic-settings` in `src/infra/config/settings.py`
- SQLModel for database models with async SQLAlchemy

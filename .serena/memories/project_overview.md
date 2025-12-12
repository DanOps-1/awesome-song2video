# Project Overview

## Purpose
Async lyrics-video mashup backend system using TwelveLabs AI for semantic video understanding. Automatically matches lyrics with video clips to generate karaoke-style videos.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, async SQLAlchemy + SQLModel
- **Database**: PostgreSQL with asyncpg
- **Queue**: Redis + ARQ for async task processing
- **AI/ML**: Whisper (transcription), TwelveLabs (video search), DeepSeek LLM (query rewriting)
- **Audio**: Demucs (vocal separation), DeepFilterNet (denoising), pydub, torchaudio
- **Video**: FFmpeg for rendering
- **Frontend**: Node.js 18+, React (two apps: user frontend port 6008, admin dashboard port 6006)

## Architecture
1. **Audio Upload** → Whisper transcribes lyrics with timestamps
2. **Lyrics Confirmation** → User reviews/edits recognized lyrics
3. **Video Matching** → TwelveLabs API matches each lyric line to video segments
4. **Rendering** → FFmpeg concatenates clips with audio and burned-in subtitles

## Key Services
- **TimelineBuilder** (`src/pipelines/matching/timeline_builder.py`): Orchestrates transcription + video search
- **RenderWorker** (`src/workers/render_worker.py`): Parallel clip extraction with FFmpeg
- **QueryRewriter** (`src/services/matching/query_rewriter.py`): Converts abstract lyrics to visual descriptions
- **LyricsFetcher** (`src/lyrics/fetcher.py`): Fetches lyrics from Netease Cloud Music API

## Database Models
- `SongMixRequest` - Main mix request entity
- `LyricLine` - Individual lyric lines with timestamps
- `VideoSegmentMatch` - Video candidates for each line
- `RenderJob` - Async render task tracking

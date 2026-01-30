<div align="center">

# Song2Video

**AI-Powered Lyrics Video Mashup Engine**

Upload a song, get an auto-generated beat-synced video mashup

[![CI](https://github.com/DanOps-1/awesome-song2video/actions/workflows/ci.yml/badge.svg)](https://github.com/DanOps-1/awesome-song2video/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/DanOps-1/awesome-song2video/branch/main/graph/badge.svg)](https://codecov.io/gh/DanOps-1/awesome-song2video)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

[中文](README.md) · [Quick Start](#quick-start) · [API Docs](http://localhost:8000/docs)

</div>

---

## What Does It Do?

```
Audio File → Auto-fetch Lyrics → AI Semantic Video Matching → Beat Sync → Final Output
```

**Core Features:**
- 🎤 **Multi-source Lyrics** - QQ Music/NetEase/Kugou/LRCLIB with auto-fallback
- 🤖 **Semantic Matching** - TwelveLabs video understanding + DeepSeek query rewriting, 100% match rate
- 🥁 **Auto Beat Sync** - CapCut-like drum beat alignment
- 🔄 **Smart Deduplication** - 80%+ clip deduplication rate

---

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/DanOps-1/awesome-song2video.git
cd awesome-song2video

# Configure API keys
cp .env.example .env
# Edit .env with TL_API_KEY and TL_INDEX_ID

docker compose up -d
```

### Local Development

```bash
# Requirements: Python 3.11+, Node 18+, FFmpeg, Redis, PostgreSQL

uv sync                                    # Python deps
cd apps/frontend && npm i && cd ../..      # Frontend deps
cp .env.example .env                       # Configure env
bash start.sh                              # Start services
```

### Access Points

| Service | URL |
|---------|-----|
| User Frontend | http://localhost:6008 |
| Admin Dashboard | http://localhost:6006 |
| API Docs | http://localhost:8000/docs |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  React Frontend (6008)  │  Admin Dashboard (6006)        │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│                   FastAPI (8000)                         │
│         Mixes API  │  Render API  │  Admin API           │
└──────────┬─────────────────────────────────┬─────────────┘
           │                                 │
     ┌─────▼─────┐                   ┌───────▼───────┐
     │   Redis   │◄─────────────────►│  ARQ Workers  │
     │   Queue   │                   │  Timeline/Render│
     └─────┬─────┘                   └───────┬───────┘
           │                                 │
     ┌─────▼─────┐                   ┌───────▼───────┐
     │ PostgreSQL│                   │ External APIs │
     │  Database │                   │ TwelveLabs    │
     └───────────┘                   │ DeepSeek      │
                                     │ Lyrics APIs   │
                                     └───────────────┘
```

**Tech Stack:** FastAPI · React · Redis/ARQ · PostgreSQL · FFmpeg · TwelveLabs · DeepSeek

---

## Configuration

### Required

| Variable | Description |
|----------|-------------|
| `TL_API_KEY` | TwelveLabs API key |
| `TL_INDEX_ID` | TwelveLabs video index ID |
| `REDIS_URL` | Redis connection URL |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | - | Query rewriting (improves match rate) |
| `BEAT_SYNC_MODE` | `onset` | Sync mode: `onset`/`action` |

---

## Development

```bash
uv run ruff check src tests    # Lint
uv run mypy src                # Type check
uv run pytest tests/           # Tests
```

---

## License

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) - Personal use allowed, commercial use prohibited

---

<div align="center">

**[DanOps-1](https://github.com/DanOps-1)** · 870657960@qq.com

</div>

<p align="center">
  <img src="https://img.icons8.com/color/96/video-editing.png" alt="Song2Video Logo" width="96" height="96">
</p>

<h1 align="center">Song2Video</h1>

<p align="center">
  <strong>AI-Powered Intelligent Lyrics Video Mashup System</strong>
</p>

<p align="center">
  Powered by TwelveLabs Video Understanding + Online Lyrics Services + DeepSeek Semantic Rewriting
</p>

<p align="center">
  <a href="https://github.com/DanOps-1/awesome-song2video/actions/workflows/ci.yml">
    <img src="https://github.com/DanOps-1/awesome-song2video/actions/workflows/ci.yml/badge.svg" alt="CI Status">
  </a>
  <a href="https://github.com/DanOps-1/awesome-song2video/actions/workflows/security-audit.yml">
    <img src="https://github.com/DanOps-1/awesome-song2video/actions/workflows/security-audit.yml/badge.svg" alt="Security Audit">
  </a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/node-18+-green.svg" alt="Node 18+">
  <a href="https://creativecommons.org/licenses/by-nc/4.0/">
    <img src="https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey.svg" alt="License">
  </a>
</p>

<p align="center">
  <a href="README.md">中文</a> •
  <a href="docs/">Docs</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="docs/DEMO.md">Demo</a> •
  <a href="#-why-song2video">Why Song2Video</a> •
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## Overview

**Song2Video** is an async lyrics-video mashup backend system that automatically matches lyrics semantics with video clips to generate high-quality beat-synced videos.

### Workflow

```
🎵 Upload Audio → 🎤 Fetch Lyrics → 🤖 AI Query Rewrite → 🎬 Video Matching → 🎯 Beat Sync → 📹 Render Output
```

### Demo

> **Note**: Demo videos and screenshots coming soon. You can run locally via [Quick Start](#-quick-start) to see it in action.

### Core Features

| Feature | Description |
|---------|-------------|
| 🎤 Multi-source Lyrics | QQ Music/NetEase/Kugou/LRCLIB with auto-fallback |
| 🤖 AI Query Rewriting | Abstract lyrics → Visual descriptions, 100% match rate |
| 🎬 Semantic Video Matching | TwelveLabs API intelligent matching |
| 🥁 Auto Beat Sync | CapCut-like rhythm synchronization |
| 🔄 Smart Deduplication | Avoid reusing same video clips |
| 🌐 Bilingual Subtitles | Chinese/English subtitle support |

---

## Why Song2Video

Comparison with traditional video editing approaches:

| Feature | Manual Editing | FFmpeg Concat | Keyword Search | **Song2Video** |
|---------|---------------|---------------|----------------|---------------|
| Semantic Understanding | ❌ | ❌ | ⚠️ Shallow | ✅ Deep |
| Auto Beat Sync | ❌ | ❌ | ❌ | ✅ Beat-aligned |
| Smart Deduplication | ❌ | ❌ | ❌ | ✅ 80%+ dedup |
| Processing Speed | 🐌 Hours | ⚡ Minutes | ⚡ Minutes | ⚡ Minutes |
| Match Accuracy | 👍 High | ❌ None | ⚠️ Medium | 👍 100% |
| Learning Curve | High | Medium | Low | **Very Low** |

---

## Quick Start

### Option 1: One-liner Bootstrap (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/DanOps-1/awesome-song2video/main/scripts/bootstrap.sh | bash
```

This script will automatically:
- ✅ Check and install dependencies (Python, Node.js, FFmpeg, Redis)
- ✅ Clone the project and configure environment
- ✅ Start all services
- ✅ Open browser to frontend

### Option 2: Docker

```bash
# 1. Clone the repository
git clone https://github.com/DanOps-1/awesome-song2video.git
cd awesome-song2video

# 2. Configure environment
cp .env.example .env
# Edit .env with your TL_API_KEY and TL_INDEX_ID

# 3. Start services
docker compose up -d
```

### Option 3: Manual Setup

<details>
<summary>Click to expand detailed steps</summary>

#### Requirements

- Python >= 3.11
- Node.js >= 18
- FFmpeg
- Redis
- PostgreSQL

#### Steps

```bash
# 1. Clone the repository
git clone https://github.com/DanOps-1/awesome-song2video.git
cd awesome-song2video

# 2. Install Python dependencies
uv sync

# 3. Install frontend dependencies
cd apps/frontend && npm install
cd ../web && npm install
cd ../..

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Start services
bash start.sh
```

</details>

### Access Points

After successful startup:

| Service | URL | Description |
|---------|-----|-------------|
| 🎨 User Frontend | http://localhost:6008 | Upload audio, generate videos |
| ⚙️ Admin Dashboard | http://localhost:6006 | Task management, monitoring |
| 📚 API Docs | http://localhost:8000/docs | Swagger interactive docs |

### Usage Steps

1. **Upload Audio** - Upload MP3/WAV audio file in the frontend
2. **Fetch Lyrics** - System auto-fetches from multiple platforms (or import manually)
3. **Confirm Lyrics** - Review and edit lyrics timeline
4. **Generate Preview** - View video clip matching results
5. **Submit Render** - One-click generate final video

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│            User Frontend (6008)  │  Admin Dashboard (6006)   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (8000)                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐ │
│  │  Mixes  │  │  Lines  │  │ Render  │  │  Admin APIs     │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌─────────────────┐      ┌─────────────────────────────────────┐
│     Redis       │      │            Workers (ARQ)            │
│  Queue + Cache  │◄────►│  Timeline Worker │ Render Worker    │
└─────────────────┘      └─────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌─────────────────┐      ┌─────────────────────────────────────┐
│   PostgreSQL    │      │          External Services          │
│    Database     │      │  TwelveLabs  │  DeepSeek  │ Lyrics  │
└─────────────────┘      └─────────────────────────────────────┘
```

### Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | FastAPI, Uvicorn, SQLModel, AsyncPG |
| **Frontend** | React, TypeScript, Vite, TailwindCSS |
| **Queue** | Redis, ARQ |
| **Video** | FFmpeg, Pydub |
| **AI** | TwelveLabs, DeepSeek, Lyrics APIs |
| **Observability** | OpenTelemetry, Structlog |

---

## API Documentation

### Main Endpoints

```http
# Create mix task
POST /api/v1/mixes
{
  "song_title": "Test Song",
  "audio_url": "https://example.com/song.mp3"
}

# Get timeline preview
GET /api/v1/mixes/{id}/preview

# Submit render
POST /api/v1/mixes/{id}/render

# Get render status
GET /api/v1/mixes/{id}/render/status
```

<details>
<summary><b>View Full API List</b></summary>

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/mixes` | POST | Create mix task |
| `/api/v1/mixes/{id}` | GET | Get task details |
| `/api/v1/mixes/{id}/fetch-lyrics` | POST | Fetch lyrics online |
| `/api/v1/mixes/{id}/import-lyrics` | POST | Import lyrics manually |
| `/api/v1/mixes/{id}/lines` | GET/POST | Manage lyric lines |
| `/api/v1/mixes/{id}/preview` | GET | Timeline preview |
| `/api/v1/mixes/{id}/render` | POST | Submit render |
| `/api/v1/mixes/{id}/analyze-beats` | POST | Beat analysis |
| `/api/v1/mixes/{id}/beats` | GET | Get beat data |
| `/api/v1/render/config` | GET/PATCH | Render config |
| `/api/v1/admin/logs` | GET | Log query |

</details>

---

## Configuration

<details>
<summary><b>Environment Variables</b></summary>

### Required

| Variable | Description |
|----------|-------------|
| `TL_API_KEY` | TwelveLabs API key |
| `TL_INDEX_ID` | TwelveLabs video index ID |
| `REDIS_URL` | Redis connection URL |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | - | DeepSeek API (query rewriting) |
| `BEAT_SYNC_ENABLED` | true | Enable beat sync |
| `BEAT_SYNC_MODE` | onset | Sync mode (onset/action) |
| `VIDEO_INTRO_SKIP_MS` | 8000 | Skip video intro (ms) |

</details>

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Query Match Rate | **100%** (with smart rewriting) |
| Video Deduplication | **> 80%** |
| Semantic Alignment | **> 90%** |
| Preview Generation | **< 3 seconds** |
| Average Alignment Offset | **≤ 200ms** |
| Fallback Rate | **< 10%** |

---

## Development

```bash
# Code quality
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src

# Run tests
uv run pytest tests/

# E2E test
uv run python scripts/dev/e2e_full_render_test.py
```

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)

- ✅ Personal learning and research allowed
- ✅ Modification and distribution allowed (with attribution)
- ❌ Commercial use not allowed

---

## Contact

- **Maintainer**: DanOps-1
- **Email**: 870657960@qq.com

---

<p align="center">
  Made with ❤️ by DanOps-1
</p>

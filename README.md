<div align="center">

# Song2Video

**AI 歌词视频混剪引擎**

上传一首歌，自动生成卡点混剪视频

[![CI](https://github.com/DanOps-1/awesome-song2video/actions/workflows/ci.yml/badge.svg)](https://github.com/DanOps-1/awesome-song2video/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/DanOps-1/awesome-song2video/branch/main/graph/badge.svg)](https://codecov.io/gh/DanOps-1/awesome-song2video)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

[English](README_EN.md) · [快速开始](#快速开始) · [API 文档](http://localhost:8000/docs)

</div>

---

## 它能做什么？

```
音频文件 → 自动获取歌词 → AI 语义匹配视频片段 → 鼓点卡点 → 输出成片
```

**核心能力：**
- 🎤 **多源歌词** - QQ音乐/网易云/酷狗/LRCLIB 自动回退
- 🤖 **语义匹配** - TwelveLabs 视频理解 + DeepSeek 查询改写，100% 匹配率
- 🥁 **自动卡点** - 类似剪映的鼓点对齐
- 🔄 **智能去重** - 80%+ 片段去重率

---

## 快速开始

### Docker（推荐）

```bash
git clone https://github.com/DanOps-1/awesome-song2video.git
cd awesome-song2video

# 配置 API 密钥
cp .env.example .env
# 编辑 .env，填入 TL_API_KEY 和 TL_INDEX_ID

docker compose up -d
```

### 本地开发

```bash
# 依赖：Python 3.11+, Node 18+, FFmpeg, Redis, PostgreSQL

uv sync                                    # Python 依赖
cd apps/frontend && npm i && cd ../..      # 前端依赖
cp .env.example .env                       # 配置环境变量
bash start.sh                              # 启动服务
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 用户前端 | http://localhost:6008 |
| 管理后台 | http://localhost:6006 |
| API 文档 | http://localhost:8000/docs |

---

## 架构

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
                                     │ 歌词服务       │
                                     └───────────────┘
```

**技术栈：** FastAPI · React · Redis/ARQ · PostgreSQL · FFmpeg · TwelveLabs · DeepSeek

---

## 配置

### 必需

| 变量 | 说明 |
|------|------|
| `TL_API_KEY` | TwelveLabs API 密钥 |
| `TL_INDEX_ID` | TwelveLabs 视频索引 ID |
| `REDIS_URL` | Redis 连接地址 |

### 可选

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | - | 查询改写（提升匹配率）|
| `BEAT_SYNC_MODE` | `onset` | 卡点模式：`onset`/`action` |

---

## 开发

```bash
uv run ruff check src tests    # Lint
uv run mypy src                # Type check
uv run pytest tests/           # 测试
```

---

## 许可证

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) - 允许学习研究，禁止商用

---

<div align="center">

**[DanOps-1](https://github.com/DanOps-1)** · 870657960@qq.com

</div>

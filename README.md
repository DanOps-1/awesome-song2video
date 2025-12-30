<p align="center">
  <img src="https://img.icons8.com/color/96/video-editing.png" alt="Song2Video Logo" width="96" height="96">
</p>

<h1 align="center">🎬 Song2Video</h1>

<p align="center">
  <strong>AI 驱动的智能歌词视频混剪系统</strong>
</p>

<p align="center">
  基于 TwelveLabs 视频理解 + 在线歌词服务 + DeepSeek 语义改写
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
  <a href="#-快速开始">快速开始</a> •
  <a href="#-核心特性">核心特性</a> •
  <a href="#-技术架构">技术架构</a> •
  <a href="#-api-文档">API 文档</a> •
  <a href="#-贡献指南">贡献指南</a>
</p>

---

## 📖 项目简介

**Song2Video** 是一个异步歌词语义混剪后端系统，自动将歌词语义与视频片段进行精准匹配，生成高质量的卡点视频。

### 工作流程

```
🎵 上传音频 → 🎤 在线歌词获取 → 🤖 AI 语义改写 → 🎬 视频片段匹配 → 🎯 节拍卡点 → 📹 渲染输出
```

### 效果展示

| 功能 | 说明 |
|------|------|
| 🎤 多源歌词获取 | QQ音乐/网易云/酷狗/LRCLIB，自动回退 |
| 🤖 AI 查询改写 | 抽象歌词 → 具体视觉描述，匹配率 100% |
| 🎬 语义视频匹配 | TwelveLabs API 智能匹配 |
| 🥁 鼓点自动卡点 | 类似剪映的节奏同步 |
| 🔄 智能去重 | 避免重复使用相同片段 |
| 🌐 双语字幕 | 中英双语支持 |

---

## 🚀 快速开始

### 环境要求

- Python >= 3.11
- Node.js >= 18
- FFmpeg
- Redis

### 一键启动

```bash
# 1. 克隆项目
git clone https://github.com/DanOps-1/awesome-song2video.git
cd awesome-song2video

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 TL_API_KEY 和 TL_INDEX_ID

# 3. Docker 启动（推荐）
docker compose up -d

# 或手动启动
bash start.sh
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 📚 API 文档 | http://localhost:8000/docs |
| 🎨 用户前端 | http://localhost:6008 |
| ⚙️ 管理后台 | http://localhost:6006 |

---

## ✨ 核心特性

<details>
<summary><b>🎵 智能音视频同步</b></summary>

- **RMS 能量分析**：自动检测人声开始位置
- **前奏跳过**：检测 >= 5 秒的纯音乐前奏自动跳过
- **词级时间戳**：片段数量从 26 个提升至 49-74 个
- **音频精准裁剪**：视频、音频、字幕完美同步

</details>

<details>
<summary><b>🤖 智能查询改写</b></summary>

- **分数阈值触发**：score >= 0.9 跳过改写，< 0.9 触发改写
- **LLM 驱动**：DeepSeek AI 将抽象歌词转为视觉描述
- **递进式策略**：最多 3 次改写，温度逐步提升
- **Tom & Jerry 优化**：卡通素材库专属提示词

</details>

<details>
<summary><b>🥁 鼓点自动卡点</b></summary>

- **双模式支持**：
  - `onset`：视频鼓点 → 音乐鼓点对齐（类似剪映）
  - `action`：视频动作点 → 音乐节拍对齐
- **5 候选容错**：渲染失败自动回退
- **严格时长检查**：禁止视频循环

</details>

<details>
<summary><b>🎬 视频处理优化</b></summary>

- **多比例支持**：16:9（默认）和 4:3
- **智能背景**：模糊背景处理不同比例
- **片头过滤**：自动跳过视频开头 8 秒
- **语义对齐**：从片段中间位置提取精彩画面

</details>

<details>
<summary><b>⚡ 高性能架构</b></summary>

- **异步队列**：Redis + ARQ 高性能任务处理
- **并行裁剪**：TaskGroup + Semaphore 控制并行
- **热加载配置**：不重启 Worker 调整并发参数
- **完整可观测性**：OpenTelemetry + Prometheus + Loki

</details>

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│            用户前端 (6008)  │  管理后台 (6006)                │
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
│    Database     │      │  TwelveLabs  │  DeepSeek  │ 歌词 API  │
└─────────────────┘      └─────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | FastAPI, Uvicorn, SQLModel, AsyncPG |
| **前端** | React, TypeScript, Vite, TailwindCSS |
| **队列** | Redis, ARQ |
| **视频** | FFmpeg, Pydub |
| **AI** | TwelveLabs, DeepSeek, 歌词服务 (QQ/NetEase/Kugou/LRCLIB) |
| **监控** | OpenTelemetry, Structlog |

---

## 📚 API 文档

### 主要接口

```http
# 创建混剪任务
POST /api/v1/mixes
{
  "song_title": "测试歌曲",
  "audio_url": "https://example.com/song.mp3"
}

# 查看时间线预览
GET /api/v1/mixes/{id}/preview

# 提交渲染
POST /api/v1/mixes/{id}/render

# 获取渲染状态
GET /api/v1/mixes/{id}/render/status
```

<details>
<summary><b>查看完整 API 列表</b></summary>

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/mixes` | POST | 创建混剪任务 |
| `/api/v1/mixes/{id}` | GET | 获取任务详情 |
| `/api/v1/mixes/{id}/fetch-lyrics` | POST | 在线获取歌词 |
| `/api/v1/mixes/{id}/import-lyrics` | POST | 手动导入歌词 |
| `/api/v1/mixes/{id}/lines` | GET/POST | 管理歌词行 |
| `/api/v1/mixes/{id}/preview` | GET | 时间线预览 |
| `/api/v1/mixes/{id}/render` | POST | 提交渲染 |
| `/api/v1/mixes/{id}/analyze-beats` | POST | 节拍分析 |
| `/api/v1/mixes/{id}/beats` | GET | 获取节拍数据 |
| `/api/v1/render/config` | GET/PATCH | 渲染配置 |
| `/api/v1/admin/logs` | GET | 日志查询 |

</details>

---

## ⚙️ 配置说明

<details>
<summary><b>环境变量</b></summary>

### 必需配置

| 变量 | 说明 |
|------|------|
| `TL_API_KEY` | TwelveLabs API 密钥 |
| `TL_INDEX_ID` | TwelveLabs 视频索引 ID |
| `REDIS_URL` | Redis 连接地址 |

### 可选配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | - | DeepSeek API（查询改写）|
| `BEAT_SYNC_ENABLED` | true | 节拍卡点开关 |
| `BEAT_SYNC_MODE` | onset | 卡点模式 (onset/action) |
| `VIDEO_INTRO_SKIP_MS` | 8000 | 跳过视频片头毫秒 |

</details>

---

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| 查询匹配成功率 | **100%**（含智能改写）|
| 视频片段去重率 | **> 80%** |
| 语义对齐准确度 | **> 90%** |
| Preview 生成时间 | **< 3 秒** |
| 平均对齐偏差 | **≤ 200ms** |
| Fallback 比例 | **< 10%** |

---

## 🧪 开发指南

```bash
# 代码检查
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src

# 运行测试
uv run pytest tests/

# E2E 测试
uv run python scripts/dev/e2e_full_render_test.py
```

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

提交前请确保：
- ✅ 代码通过 Ruff 和 Mypy 检查
- ✅ 添加了相应的测试用例
- ✅ 更新了相关文档

---

## 📁 项目结构

```
.
├── src/                  # 后端源代码
│   ├── api/              # FastAPI 路由
│   ├── audio/            # 音频处理
│   ├── services/         # 业务服务
│   └── workers/          # 后台任务
├── apps/
│   ├── frontend/         # 用户前端 (React)
│   └── web/              # 管理后台 (React)
├── tests/                # 测试用例
├── scripts/              # 工具脚本
└── docs/                 # 文档
```

---

## 📜 许可证

本项目采用 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 许可证

- ✅ 允许个人学习和研究
- ✅ 允许修改和分发（需注明原作者）
- ❌ 不允许商业用途

---

## 📮 联系方式

- **项目负责人**：DanOps-1
- **Email**：870657960@qq.com

---

<details>
<summary><b>📝 更新日志</b></summary>

### v0.5.0 (2025-12-14)
- 🆕 视频比例选择功能
- 🆕 双语字幕支持
- 🆕 实时日志查看
- 🆕 节拍分析 API

### v0.4.0 (2025-12-13)
- 🆕 鼓点自动卡点功能
- 🆕 5 候选容错机制

### v0.3.0 (2025-11-30)
- 🆕 用户前端和管理后台
- 🆕 渲染进度追踪

### v0.2.0 (2025-11-18)
- 🆕 智能查询改写系统
- 🆕 视频片段去重机制

### v0.1.0 (2025-11-14)
- 🎉 初始版本发布

</details>

---

<p align="center">
  Made with ❤️ by DanOps-1
</p>

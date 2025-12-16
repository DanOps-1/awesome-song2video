# 项目目录结构

**版本**: v1.0
**最后更新**: 2025-12-16

---

## 顶层目录

```
awsome-song2video/
├── src/                    # 源代码
├── tests/                  # 测试代码
├── docs/                   # 文档
├── scripts/                # 脚本工具
├── frontend/               # 用户前端 (React)
├── web/                    # 管理后台前端 (React)
├── media/                  # 媒体文件目录
├── data/                   # 数据目录
├── artifacts/              # 构建产物
├── .claude/                # Claude Code 配置
└── .specify/               # 项目规格配置
```

---

## 源代码 (src/)

```
src/
├── api/                    # FastAPI 路由层
│   ├── main.py            # 应用入口
│   └── v1/
│       └── routes/
│           ├── mixes.py           # 混剪任务 API
│           ├── mix_lines.py       # 歌词行管理 API
│           ├── preview.py         # 预览 API
│           ├── render.py          # 渲染 API
│           └── admin/             # 管理后台 API
│               ├── tasks.py       # 任务管理
│               ├── logs.py        # 日志查看器
│               └── status.py      # 系统状态
│
├── audio/                  # 音频处理模块
│   ├── beat_detector.py   # 节拍检测 (librosa)
│   ├── onset_detector.py  # 鼓点检测
│   └── transcriber.py     # Whisper 转录
│
├── domain/                 # 领域模型
│   └── models.py          # 数据库模型定义
│       ├── SongMixRequest
│       ├── LyricLine
│       ├── VideoSegmentMatch
│       ├── RenderJob
│       └── BeatAnalysisData
│
├── infra/                  # 基础设施层
│   ├── config/
│   │   └── settings.py    # 配置管理 (pydantic-settings)
│   ├── logging/
│   │   └── setup.py       # 日志配置 (structlog)
│   └── persistence/
│       ├── database.py    # 数据库连接
│       └── repositories/  # 数据访问层
│           ├── song_mix_repository.py
│           └── render_job_repository.py
│
├── lyrics/                 # 歌词获取模块
│   ├── fetcher.py         # 歌词获取入口
│   └── sources/           # 各平台适配器
│       ├── qq_music.py
│       ├── netease.py
│       ├── kugou.py
│       └── lrclib.py
│
├── pipelines/              # 处理管道
│   ├── matching/          # 视频匹配管道
│   │   └── timeline_builder.py  # 时间线构建
│   ├── rendering/         # 渲染管道
│   │   └── renderer.py
│   └── editing/           # 编辑管道
│       └── timeline_editor.py   # 时间线编辑器
│
├── retrieval/              # 视频检索模块
│   ├── protocol.py        # 检索协议定义
│   ├── factory.py         # 检索器工厂
│   ├── twelvelabs/        # TwelveLabs 检索器
│   │   └── retriever.py
│   ├── clip/              # CLIP 本地检索 (备用)
│   └── vlm/               # VLM 检索 (备用)
│
├── services/               # 业务服务
│   └── matching/          # 匹配服务
│       ├── twelvelabs_client.py     # TwelveLabs API 封装
│       ├── twelvelabs_video_fetcher.py  # 视频下载
│       ├── query_rewriter.py        # 查询改写 (DeepSeek)
│       └── beat_aligner.py          # 节拍对齐
│
├── video/                  # 视频处理
│   └── ffmpeg_utils.py    # FFmpeg 工具函数
│
└── workers/                # 后台任务 (ARQ)
    ├── timeline_worker.py # 时间线生成 Worker
    └── render_worker.py   # 视频渲染 Worker
```

---

## 测试 (tests/)

```
tests/
├── contract/              # 契约测试
│   └── api/
│       ├── test_mixes.py
│       ├── test_render_config.py
│       └── test_health.py
├── integration/           # 集成测试
│   └── render/
│       ├── test_parallel_clip_pipeline.py
│       └── test_render_fallbacks.py
└── unit/                  # 单元测试
    ├── test_timeline_builder.py
    └── test_lyrics_fetcher.py
```

---

## 数据目录 (data/)

```
data/
├── db/                    # 数据库文件
│   └── dev.db            # SQLite 开发数据库
└── qdrant/               # 向量数据库 (CLIP 检索用)
```

---

## 媒体目录 (media/)

```
media/
├── uploads/              # 用户上传的音频
├── videos/               # 测试/示例视频
├── screenshots/          # 截图
└── fallback/             # 回退资源
    └── clip_placeholder.mp4  # 占位视频
```

---

## 构建产物 (artifacts/)

```
artifacts/
├── renders/              # 渲染输出
│   ├── {job_id}.mp4     # 渲染视频
│   └── {job_id}.srt     # 字幕文件
├── render_tmp/           # 渲染临时文件 (自动清理)
└── previews/             # 预览文件
```

---

## 脚本 (scripts/)

```
scripts/
├── dev/                   # 开发脚本
│   ├── e2e_test.py       # 端到端测试
│   ├── e2e_full_render_test.py
│   └── run_audio_demo.py
└── media/                 # 媒体处理脚本
    └── create_placeholder_clip.py
```

---

## 文档 (docs/)

```
docs/
├── ARCHITECTURE.md       # 系统架构文档
├── SYSTEM_FLOW.md        # 完整运行流程
├── DEMO.md               # 功能演示指南
├── PROJECT_STRUCTURE.md  # 项目目录结构 (本文档)
├── QUERY_REWRITE_MODES.md  # 查询改写模式说明
├── MARENGO_CONFIG.md     # TwelveLabs Marengo 配置
├── lyrics_mix_runbook.md # 运维手册
└── observability/        # 可观测性文档
    └── render_dashboard.md
```

---

## 前端 (frontend/ & web/)

```
frontend/                  # 用户前端
├── src/
│   ├── components/       # React 组件
│   ├── pages/            # 页面
│   ├── api/              # API 调用
│   └── styles/           # 样式
├── package.json
└── vite.config.ts

web/                       # 管理后台前端
├── src/
│   ├── components/
│   ├── pages/
│   │   ├── Dashboard/    # 仪表盘
│   │   ├── Tasks/        # 任务管理
│   │   ├── Status/       # 系统状态
│   │   └── Logs/         # 日志查看
│   └── api/
├── package.json
└── vite.config.ts
```

---

## 配置文件

```
根目录配置文件:
├── .env                   # 环境变量 (不提交)
├── .env.example           # 环境变量模板
├── pyproject.toml         # Python 项目配置
├── CLAUDE.md              # Claude Code 项目指南
├── start.sh               # 启动脚本
└── docker-compose.yml     # Docker 配置 (可选)
```

---

## 关键模块说明

### 1. 领域模型 (domain/)
定义核心业务实体，使用 SQLModel 同时支持 ORM 和 Pydantic 验证。

### 2. 管道层 (pipelines/)
处理复杂业务流程，如时间线构建、视频渲染等。

### 3. 服务层 (services/)
封装外部服务调用，如 TwelveLabs API、DeepSeek API。

### 4. 仓储层 (infra/persistence/)
数据访问抽象，支持数据库操作。

### 5. 检索层 (retrieval/)
视频检索抽象，支持多种检索器实现（工厂模式）。

### 6. Worker 层 (workers/)
异步任务处理，使用 ARQ + Redis。

---

## 命名约定

| 类型 | 命名规则 | 示例 |
|------|---------|------|
| 模块目录 | 小写下划线 | `song_mix/`, `render_job/` |
| Python 文件 | 小写下划线 | `timeline_builder.py` |
| 类名 | PascalCase | `TimelineBuilder`, `SongMixRequest` |
| 函数/方法 | 小写下划线 | `build_timeline()`, `get_candidates()` |
| 常量 | 大写下划线 | `DEFAULT_LIMIT`, `MAX_RETRY` |
| 环境变量 | 大写下划线 | `TL_API_KEY`, `REDIS_URL` |

---

**文档结束**

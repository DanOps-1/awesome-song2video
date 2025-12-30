# Implementation Plan: 移除本地依赖，纯云端化

**Branch**: `002-remove-local-deps` | **Date**: 2025-12-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-remove-local-deps/spec.md`

## Summary

本次重构旨在移除项目中的重型本地依赖（Whisper ASR、torch、transformers 等），简化部署配置要求，使项目可在 2GB 内存、无 GPU 的服务器上运行。

**核心变更**：
- 移除 Whisper ASR → 使用在线歌词搜索服务（已有 LyricsFetcher）替代
- 移除 torch/transformers → 消除 GPU 依赖
- 保留 librosa（节拍检测，纯 CPU）和 FFmpeg（视频渲染）
- 保持 TwelveLabs API 作为唯一的视频搜索方案

## Technical Context

**Language/Version**: Python 3.11+（已有）
**Primary Dependencies**: FastAPI, SQLModel, structlog, httpx, librosa, FFmpeg
**Storage**: PostgreSQL + Redis（已有）
**Testing**: pytest + pytest-asyncio
**Target Platform**: Linux server (2GB RAM, no GPU)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: 歌词搜索 < 5s，视频匹配 < 3s（已有）
**Constraints**: 无 GPU，2GB 内存，Docker 镜像 < 2GB
**Scale/Scope**: 保持现有规模

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|------|------|------|
| I. Documentation First | ✅ Pass | spec.md 已完成，plan.md 进行中 |
| II. Async-First | ✅ Pass | 不影响异步架构 |
| III. Code Quality | ✅ Pass | 移除代码需通过 Ruff/mypy |
| IV. Security First | ✅ Pass | 不涉及安全变更 |
| V. Data Authenticity | ✅ Pass | 歌词来源保持真实（在线服务） |
| VI. Simplicity | ✅ Pass | 移除复杂度，符合 YAGNI |
| VII. Observability | ✅ Pass | 保留日志系统 |
| VIII. Test Coverage | ✅ Pass | 需更新测试，移除废弃测试 |

**Constitution 合规**: 本次重构完全符合 Constitution 原则，特别是简洁性原则。

## Project Structure

### Documentation (this feature)

```text
specs/002-remove-local-deps/
├── spec.md              # 规格说明
├── plan.md              # 本文件
├── research.md          # Phase 0 研究输出
├── data-model.md        # Phase 1 数据模型（本次无变更）
├── quickstart.md        # Phase 1 验证步骤
├── contracts/           # Phase 1 API 合约（本次无变更）
└── tasks.md             # Phase 2 任务列表
```

### Source Code (repository root)

```text
src/
├── api/                 # FastAPI 路由（无变更）
├── audio/               # 音频处理
│   ├── beat_detector.py # 保留（librosa）
│   ├── onset_detector.py# 保留（librosa）
│   └── transcriber.py   # 🗑️ 删除（Whisper）
├── domain/              # 领域模型（无变更）
├── infra/               # 基础设施
│   └── config/settings.py # 移除 Whisper 配置
├── lyrics/              # 歌词处理
│   └── fetcher.py       # 保留（在线搜索）
├── pipelines/           # 处理管道
│   └── matching/
│       └── timeline_builder.py # 移除 Whisper 路径
├── retrieval/           # 检索层（无变更）
├── services/            # 服务层
│   └── matching/        # 匹配服务（无变更）
└── workers/             # 后台任务
    ├── render_worker.py # 无变更
    └── timeline_worker.py # 移除 transcribe 任务

tests/
├── contract/            # 契约测试（无变更）
├── integration/         # 集成测试（更新）
└── unit/                # 单元测试（移除废弃测试）
```

**Structure Decision**: 保持现有 `src/` 布局，仅删除 Whisper 相关文件和代码。

## Complexity Tracking

> 无违反 Constitution 的情况，不需要记录。

---

## Phase 0: Research

### 需要研究的问题

1. **Whisper 代码分布**: 识别所有 Whisper 相关代码位置
2. **依赖关系**: 确定可安全移除的依赖包
3. **API 影响**: 识别受影响的 API 端点
4. **测试影响**: 识别需要移除或更新的测试

### 研究输出

见 [research.md](./research.md)

---

## Phase 1: Design

### 数据模型变更

本次重构不涉及数据模型变更，现有模型保持不变：
- `SongMixRequest.status`: 移除 `transcribing` 状态（或保留但不使用）
- 其他模型无变更

见 [data-model.md](./data-model.md)

### API 合约变更

以下 API 端点将受影响：
- `POST /api/v1/mixes/{id}/transcribe` → 移除或修改为错误提示
- `POST /api/v1/mixes/{id}/fetch-lyrics` → 保持不变，成为主要歌词获取方式

见 [contracts/README.md](./contracts/README.md)

### 快速验证

见 [quickstart.md](./quickstart.md)

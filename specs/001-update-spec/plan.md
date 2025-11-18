# 实施计划：需求与实现对齐更新

**分支**：`001-update-spec-plan` | **日期**：2025-11-17 | **规格**：`/specs/001-update-spec/spec.md`
**输入**：基于 `/specs/001-update-spec/spec.md` 的功能需求文档

**提示**：本模板由 `/speckit.plan` 命令生成。填写内容必须使用简体中文，并明确说明如何满足宪章提出的异步、分层、测试、可观测性、媒资片段按需拉取、歌词细粒度分句与目录/命令一致性要求（`src/api/v1`、`src/domain/...`、`src/pipelines/...`、`src/infra/...`、`src/workers/...`、`tests/...` 以及 `uvicorn/arq/pytest/scripts/dev/seed_demo.sh` 等需逐一说明豁免与调整）。

## 摘要

本迭代需将歌词时间线 manifest、fallback 告警与渲染指标完全对齐现有实现，形成可供策划审核与运维监控的 API/日志/指标闭环。技术方案沿用 FastAPI + Arq + SQLModel + Redis/asyncpg + structlog + OTEL，针对媒资按需截取（HLS 按时间窗拉取）与歌词细粒度分句进行补强，并确保所有指标写入 `SongMixRequest.metrics.preview` 与 `RenderJob.metrics.render`。

计划重点包括：统一 preview service/manifest 结构、渲染 worker 对齐计算、fallback/MinIO TODO 追踪、观测面（Prometheus/Loki）扩展，以及在 runbook/quickstart 中给出复现/排查指南。所有文档、测试与日志遵循中文/结构化要求。

## 技术背景

> 请逐项说明现状与待决事项，如与默认要求不符需标注“NEEDS CLARIFICATION”。

**语言/版本**：Python 3.11 + asyncio（FastAPI、Arq、uvloop）——符合宪章，暂无豁免。
**主要依赖**：FastAPI（API 层）、httpx（TwelveLabs/MinIO 通信）、SQLModel+asyncpg（PostgreSQL 15）、Redis+Arq（异步任务）、structlog+OTEL（观测）、FFmpeg+Whisper+Pydub（媒资处理）、TwelveLabs SDK（语义检索）。
**存储**：PostgreSQL（SongMixRequest/RenderJob 持久化）+ Redis（队列），均使用异步驱动；MinIO/S3 尚未启用，产物暂存本地并在日志中记录 TODO。
**测试**：pytest + pytest-asyncio + ruff + mypy；另外提供契约测试（preview/render API）、integration fallback flow 与 Golden manifest。
**目标平台**：Linux 服务端（CI/CD + 本地开发），通过 uvicorn + Arq worker 启动。
**项目形态**：单体后端（API + worker + pipelines），遵循现有 `src/...` 结构。
**性能目标**：SC-001 要求 `/preview` 在 2s 内返回完整 manifest；SC-002 要求 95% 渲染任务 `avg_delta_ms ≤200`、`max_delta_ms ≤400`；render worker 并发 3（可配）。
**约束**：TwelveLabs API 调用配额、MinIO 未启用导致需本地 fallback；需遵守媒资按需截取与歌词分句原则，保持结构化日志。
**规模/范围**：影响 preview service、render worker、routes、metrics/observability、docs/runbook，涉及 3 条用户故事 + 24 个任务；接口 `/preview`、`/render` 以及 worker job。
**运行命令**：`uvicorn src.api.main:app --reload --port 8080`、`arq src.workers.timeline_worker.WorkerSettings`、`arq src.workers.render_worker.WorkerSettings`、`pytest && ruff check && mypy`、`scripts/dev/seed_demo.sh`、`scripts/dev/run_audio_demo.py`；HLS 片段拉取通过 render worker 自动触发，临时文件位于 `artifacts/render_tmp/` 并在任务结束后清理。

## 宪章符合性检查

*必须在进入 Phase 0 研究前完成，并在 Phase 1 结束后复核。*

1. ✅ 基于 Python 3.11、FastAPI/Arq/httpx，全链路异步。
2. ✅ 维持 `services/preview_service.py`、`workers/render_worker.py`、`infra/persistence/*` 等分层，接口互调通过仓储或 OTEL helper，禁止跨层访问。
3. ✅ 所有文档/日志/模板已使用简体中文，新增内容继续遵守。
4. ✅ 任务清单涵盖 pytest-asyncio、契约、集成与 Golden 测试，并要求 `pytest && ruff && mypy`。
5. ✅ structlog JSON + OTEL 指标（preview/render）+ 语义化版本在 docs/runbook 中体现，变更前在 specs/tasks 声明影响面。
6. ✅ 渲染 worker 只按需下载 HLS 片段（无整段持久化），lyrics ingest/preview service 在 manifest 前进行标点分句与时间窗再分配；指标记录在 metrics 字段。
7. ✅ 遵守既定目录与命令：src/api、domain、pipelines、infra、workers、tests（unit/contract/integration/golden），所有脚本通过 README/Runbook 对齐。

## 项目结构

### 默认目录（歌词语义混剪）

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

> 若功能涉及新增模块或目录，请在下方结构决策中说明真实路径与职责，并同步 README/AGENTS.md。

### 文档（本功能）

```text
specs/[###-feature]/
├── plan.md              # 本文件，由 /speckit.plan 生成
├── research.md          # Phase 0 产物（/speckit.plan）
├── data-model.md        # Phase 1 产物（/speckit.plan）
├── quickstart.md        # Phase 1 产物（/speckit.plan）
├── contracts/           # Phase 1 产物（/speckit.plan）
└── tasks.md             # Phase 2 产物（/speckit.tasks，非本命令生成）
```

### 源码（仓库根目录）

> 请选择适用结构并删除无关选项，替换为真实目录路径。

```text
# 单体项目（默认）
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# Web 应用（前后端）
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# 移动 + API
api/
└── [与 backend 相同布局]
ios/ 或 android/
└── [平台模块、UI 流程、平台测试]
```

**结构决策**：继续使用现有单体仓库结构。API 层 `src/api/v1/routes/{preview,render}.py` 暴露 REST 接口；业务逻辑在 `src/services/{preview,render}_*.py`；数据访问在 `src/infra/persistence/repositories/*.py`；媒资处理/渲染在 `src/workers/render_worker.py`；可观测性 helper 位于 `src/infra/observability/`；测试分布在 `tests/{unit,contract,integration,golden}/`。歌词分句逻辑位于 `src/pipelines/matching/timeline_builder.py`，渲染剪辑使用 `src/services/matching/twelvelabs_video_fetcher.py` HLS 截取。

## 复杂度追踪

> 仅当“宪章符合性检查”存在未通过项时填写，用于记录豁免理由与补偿措施。

| 违反项 | 必要性说明 | 被否决的更简单方案 |
|---------|------------|----------------------|
| 无 | — | — |

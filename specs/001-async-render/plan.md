# 实施计划：渲染 Worker 并行异步裁剪

**分支**：`001-async-render` | **日期**：2025-11-19 | **规格**：[specs/001-async-render/spec.md](spec.md)
**输入**：基于 `/specs/001-async-render/spec.md` 的功能需求文档

**提示**：本模板由 `/speckit.plan` 命令生成。填写内容必须使用简体中文，并明确说明如何满足宪章提出的异步、分层、测试、可观测性、查询改写与 LLM 使用、媒资片段按需拉取、歌词细粒度分句、片段去重/语义对齐以及目录/命令一致性要求（`src/api/v1`、`src/domain/...`、`src/pipelines/...`、`src/infra/...`、`src/workers/...`、`tests/...` 以及 `uvicorn/arq/pytest/scripts/dev/seed_demo.sh` 等需逐一说明豁免与调整）。

## 摘要

本特性需要把渲染 Worker 中的 clip 裁剪流程从串行改为受控的并行异步执行，确保多段歌词可以在限定并发下快速截取 TwelveLabs HLS 片段，并在 CDN/HLS 异常时回退到本地素材或占位片段。方案将在 `_extract_clips` 处引入异步任务池、统一的重试与降级策略，并新增结构化日志与 Prometheus 指标来跟踪每条 clip 的状态、耗时与并发槽位使用情况。

同时需扩展 `RenderJob.metrics.render` 中的统计字段，记录裁剪阶段的平均耗时、失败数与峰值并发；新增配置项 `render_clip_concurrency` 与热加载通道，配合现有 `arq src.workers.render_worker.WorkerSettings` 命令即可生效。方案保持媒资按需截取、lyrics 分句及 timeline 结构不变，仅在渲染阶段提升吞吐并补齐监控。

## 技术背景

> 请逐项说明现状与待决事项，如与默认要求不符需标注“NEEDS CLARIFICATION”。

**语言/版本**：Python 3.11 + asyncio（结合 `anyio.to_thread`/`asyncio.TaskGroup` 管理并发），遵循异步优先准则。
**主要依赖**：`twelvelabs` SDK（检索 + retrieve）、`structlog`（JSON 日志）、`OpenTelemetry` + Prometheus/Loki 导出、`FFmpeg` CLI（按需裁剪）、`redis-asyncio`/Arq（worker 调度）、`SQLModel` + asyncpg（持久化 render job 状态）。
**存储**：PostgreSQL 15（`RenderJob`、metrics）、Redis 7（队列与潜在配置热加载通道），均已存在异步驱动；文件输出仍在 `artifacts/renders/`。
**测试**：沿用 `pytest + pytest-asyncio + ruff + mypy --strict`，并为新并行调度引入单元测试（TaskGroup 行为、重试策略）与集成测试（Arq worker 级别）。
**目标平台**：Linux 服务端 Worker（Arq + Python），运行于已有渲染节点。
**项目形态**：单体仓库（src + workers + tests），与现有目录完全一致。
**性能目标**：clip 裁剪并行度默认 4，支持调至 6；单曲 60 段需在 20 分钟内完成，单 clip P95 < 45s，峰值并发受配置约束。
**约束**：TwelveLabs API 速率限制（需 token bucket）、CDN 带宽、FFmpeg 进程资源、临时目录磁盘占用；必须保持每个 clip 按需截取，不得保留全量 MP4。
**规模/范围**：影响 `src/workers/render_worker.py`、`src/services/matching/twelvelabs_video_fetcher.py`、`src/infra/observability/*` 与相关测试，新增配置与指标；对 `RenderJob.metrics.render` 做 schema 扩展。
**运行命令**：`arq src.workers.render_worker.WorkerSettings`（执行并行裁剪）、`arq src.workers.timeline_worker.WorkerSettings`（上下游依赖）、`uvicorn src.api.main:app --reload --port 8080`（无变更但需验证 API 不受影响）、`pytest && ruff check && mypy`（验证并行模块）、`scripts/dev/seed_demo.sh`（构造测试请求）。涉及媒资拉取的渲染流程仍通过 `twelvelabs.retrieve`+HLS，临时文件位于 `artifacts/render_tmp/`，任务结束即删除。

**配置热加载方案**：采用 Redis Pub/Sub 频道 `render:config`，Worker 常驻订阅并热更新（见 research R1）。

**占位片段素材**：统一使用 `media/fallback/clip_placeholder.mp4`（3 秒黑屏 + beep），必要时复制并重封装（见 research R2）。

## 宪章符合性检查

*必须在进入 Phase 0 研究前完成，并在 Phase 1 结束后复核。*

1. 是，Worker 继续使用 Python 3.11 与 asyncio/TaskGroup，阻塞 FFMpeg 调用包裹在 `asyncio.to_thread` 中，无需豁免。
2. 是，调度逻辑仍位于 `src/workers/render_worker.py`，HLS 下载封装在 `src/services/matching/twelvelabs_video_fetcher.py`，新增的指标输出通过 `src/infra/observability`；各层通过现有接口交互。
3. 是，计划、规格、日志字段等均按中文描述，新增字段命名采用蛇形英文并在文档中解释。
4. 是，将补充分布式 TaskGroup 的单测、渲染 Worker 的集成测试，以及现有 `pytest && ruff check && mypy` CI；不需要豁免。
5. 是，新增 `clip_task_id`、`clip_status`、`parallel_slot` 日志字段，Prometheus 指标覆盖并发、耗时、失败率，并在版本说明中记录对 API/数据的兼容影响。
6. 是，媒资继续按需截取（HLS + FFmpeg `-ss` + `-t`），歌词细粒度分句由 timeline builder 负责且未修改；渲染 metrics 新增 `clip_stats` 供对齐/耗时分析。
7. 是，仍在默认目录内实现，不新增命令；标准命令 `uvicorn`、`arq timeline_worker`、`arq render_worker`、`pytest && ruff check && mypy`、`scripts/dev/seed_demo.sh` 均适用。

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

**结构决策**：沿用歌词语义混剪单体布局；本次仅改动 `src/workers/render_worker.py`（并行调度、指标）、`src/services/matching/twelvelabs_video_fetcher.py`（缓存/重试 Hook）、`src/infra/observability/*`（指标导出）以及 `tests/*`，不新增目录，保持 API/worker/infra/domain 分层职责。

## Phase 0：研究任务

| 编号 | 研究主题 | 触发原因 |
|------|-----------|----------|
| R1 | `render_clip_concurrency` 热加载机制（Redis pub/sub vs 配置轮询） | 技术背景中的 **NEEDS CLARIFICATION A**，必须确定实现方式避免重启 worker |
| R2 | 占位片段素材格式与存储位置 | 技术背景中的 **NEEDS CLARIFICATION B**，确保 fallback 输出一致 |
| R3 | TwelveLabs HLS 并行裁剪与速率限制的最佳实践 | 关键依赖（TwelveLabs SDK/HLS）需要明确可接受的并发、token bucket 策略 |
| R4 | Python TaskGroup + FFmpeg 阻塞任务的结构化并发模式 | 关键技术选型，避免阻塞事件循环并保证日志/指标可关联 |

上述研究将在 `specs/001-async-render/research.md` 中形成决策记录，完成后再进入 Phase 1。

## 复杂度追踪

> 仅当“宪章符合性检查”存在未通过项时填写，用于记录豁免理由与补偿措施。

| 违反项 | 必要性说明 | 被否决的更简单方案 |
|---------|------------|----------------------|
| [示例：新增第 4 个子项目] | [当前需求] | [为何 3 个项目不足] |
| [示例：Repository 模式] | [具体问题] | [为何直接访问不可行] |

## 宪章复核（Phase 1 后）

- Phase 0/1 产物（research/data-model/contracts/quickstart）均遵守异步、中文与可观测性要求；未新增豁免。
- 热加载与占位片段方案均保证媒资按需截取与日志指标可追溯。
- 数据模型扩展及新 API 合同未破坏目录结构或标准命令。

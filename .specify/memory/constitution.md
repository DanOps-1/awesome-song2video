<!--
Sync Impact Report
Version change: 1.3.0 -> 1.4.0
Modified principles:
- 附加约束与技术栈：新增“媒资片段拉取”“歌词细粒度分句”，强化 manifest 粒度与下载策略
Added sections:
- 无
Removed sections:
- 无
Templates requiring updates:
- ✅ .specify/templates/plan-template.md（加入媒资片段/分句合规检查）
- ✅ .specify/templates/spec-template.md（提醒描述媒资片段与分句需求）
- ✅ .specify/templates/tasks-template.md（加入相关任务提示）
Follow-up TODOs:
- 无
-->

# 十二实验室异步平台 Constitution

## Core Principles

### 原则一：Python 3.11+ 异步优先

- **强制要求**：所有运行时代码、脚本与研发样例必须以 Python ≥3.11 实现，并默认采用 `asyncio` / `async`·`await` 语法与异步安全的第三方库（如 `httpx`、`aiofiles`）。禁止将阻塞式实现作为首选方案，确需同步 fallback 时必须在设计文档中取得豁免。
- **理由**：3.11 引入的结构化并发、TaskGroup 与性能改进是平台性能和一致性的基础，异步范式能够最大化 I/O 吞吐并降低上下文切换成本。

### 原则二：分层模块与类职责清晰

- **强制要求**：业务能力需划分为独立模块，每个模块对外暴露至少一个职责单一的类；模块之间通过接口或消息总线交互，禁止跨层访问私有实现。公共类型与 DTO 须放置在共享契约包中。
- **理由**：明确的分块结构可降低耦合度，使异步调用链易于追踪，并为后续替换实现或横向扩展提供清晰边界。

### 原则三：中文优先的知识传递

- **强制要求**：所有文档、代码注释、提交信息、模板内容与评审反馈均需以简体中文撰写；当必须引用英文术语时，需在首次出现处给出中文解释或括注。生成式输出亦需遵循此规则。
- **理由**：中文是团队协作与知识沉淀的统一语域，可避免理解偏差并提升交付效率，尤其在多地协作与快速交接场景中。

### 原则四：异步可测与自动化守护

- **强制要求**：每个模块合入前必须具备 `pytest-asyncio`（或等效框架）的单元测试、关键路径的契约/集成测试以及覆盖成功与失败分支的负载基准。CI/CD 流水线需执行静态检查（mypy/ruff）、安全扫描与最少一条端到端异步链路验证。
- **理由**：异步代码对时序高度敏感，只有借助系统性的自动化测试与分析工具，才能在早期发现竞态、饥饿或资源泄漏问题。

### 原则五：可观测、安全与版本纪律

- **强制要求**：所有服务与脚本必须输出结构化日志（JSON + trace_id）、关键指标（延迟、吞吐、错误率）以及可关联的安全事件审计，并使用 OpenTelemetry（OTLP → Prometheus/Loki）+ structlog 形成统一追踪证据；混剪预览、渲染与字幕流程必须记录并对外暴露画面对齐/字幕延迟指标。公共接口与 Arq/worker 作业需遵循语义化版本号，任何破坏性变更都要提前一个迭代在规范与任务文档中给出迁移策略。
- **理由**：高质量可观测性与明确版本边界是定位异步系统问题、支撑音视频合规与调度回滚的前提，字幕与画面对齐数据也是衡量混剪输出可用性的直接证据。

## 附加约束与技术栈

- **运行环境**：默认基于 Linux + Python 3.11，推荐启用 `uvloop`、`asyncpg`、`aiohttp/httpx` 等成熟异步库；如需引入新依赖，必须说明事件循环兼容性与类型支持情况。
- **技术栈基线**：API/worker 层统一采用 FastAPI + httpx、TwelveLabs Python SDK（语义检索）、SQLModel + asyncpg（PostgreSQL 15）、Redis 7 + Arq（异步任务）、FFmpeg CLI + Whisper + Pydub（音视频处理）、OpenTelemetry + structlog（观测）。引入其他方案前必须列出与现有栈的互操作与替换策略。
- **配置与密钥**：采纳分层配置（本地 `.env`、CI Secret、运行时参数），严禁在仓库中存放明文密钥；所有 I/O 必须通过具备超时、重试与熔断能力的客户端封装。
- **外部 API 与媒资安全**：TwelveLabs、MinIO/S3、对象存储及任何第三方接口都必须实现 token bucket、指数退避与 fallback 逻辑；媒资文件需以 `media/{audio,video}/{video_id}.ext` 管理并配套清晰的清理策略，禁止临时文件泄漏。
- **目录结构与职责映射**：仓库必须保持 `src/api/v1/`、`src/domain/{models,services}/`、`src/pipelines/{lyrics_ingest,matching,rendering}/`、`src/infra/{persistence,messaging,observability}/`、`src/workers/{timeline_worker,render_worker}.py` 以及 `tests/{unit,contract,integration,golden}/` 等目录与 README、AGENTS.md 描述一致；新增模块须在相应层建模并在规格/计划中交代职责。
- **时间线预览与对齐**：后端必须提供 JSON manifest 接口（逐句返回素材来源、起止时间、置信度），并在 `SongMixRequest.metrics.preview`/`metrics.render` 中记录平均及最大字幕延迟；任何缺失候选的歌词需明确 fallback 策略并提示人工补片。
- **媒资片段拉取**：所有 TwelveLabs/MinIO 视频下载必须基于 `retrieve` API 或等效 HLS 流按需截取所需时间窗，禁止无期限保存整段 MP4；临时文件需放置受管控目录并在作业结束后清理，日志必须记录目标 video_id 与片段跨度。
- **歌词细粒度分句**：Whisper 或歌词输入在生成 manifest 前必须按换行与常见标点切分，保证每条记录对应一行歌词；如原始片段仍过长，需按字符比例重新分配时间窗以确保字幕与画面对齐。
- **文档与范式**：规范文档、模板与代码注释需用中文撰写并保持 ≤100 字的段落长度，以便快速复用；所有自动生成的文件需记录触发命令与时间戳。
- **类与模块命名**：使用全拼或行业通用词汇，避免含糊缩写；模块目录须与职责一致（如 `async_services/`, `domain_models/`, `protocols/`）。
- **标准开发命令**：日常联调必须使用 `uvicorn src.api.main:app --reload --port 8080`、`arq src.workers.timeline_worker.WorkerSettings`、`arq src.workers.render_worker.WorkerSettings`、`pytest && ruff check && mypy` 与 `scripts/dev/seed_demo.sh`；若需新增或替换命令，必须同步 README、模板并在 PR 中写明原因与影响。

## 开发流程与质量门槛

- **Spec → Plan → Tasks 链路**：任何开发工作都需先通过 `/speckit.spec`（需求）、`/speckit.plan`（方案）和 `/speckit.tasks`（执行）三个模板生成文档，并在“Constitution Check”中确认五项核心原则未被违反。
- **评审与验收**：合并请求至少需两名熟悉异步栈的审阅者；评审重点在于异步语义、模块边界、中文资料完整度与测试覆盖率。验收必须附带日志样例与指标截图。
- **发布控制**：版本号采用 `MAJOR.MINOR.PATCH`；凡涉及公共契约调整或安全策略新增，即视为 MINOR 以上改动，需在版本说明中提供迁移步骤与滚动回退策略。

## Governance

- **修订流程**：任何人可提交宪章修订提案，需在 PR 中列明影响面、需要同步的模板文件以及计划的生效日期；经项目负责人与至少一名架构负责人双重批准后方可合入。
- **版本策略**：宪章采用语义化版本；新增原则或重大流程调整触发 MINOR+ 版本，破坏性治理变更触发 MAJOR，措辞澄清或轻微细化记为 PATCH。版本更新需在 Sync Impact Report 中说明原因。
- **合规审查**：每个迭代结束时，技术负责人需对照五项原则与附加约束执行抽查，并记录至 `docs/compliance/<迭代>.md`（若暂未创建需新建）。发现违规需在两周内补救或提交豁免申请。

**Version**: 1.4.0 | **Ratified**: 2025-11-11 | **Last Amended**: 2025-11-17

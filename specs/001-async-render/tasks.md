# 任务清单：渲染 Worker 并行异步裁剪

**输入**：`/specs/001-async-render/` 下的设计文档  
**前置**：plan.md（必填）、spec.md（用户故事）、research.md、data-model.md、contracts/

**测试说明**：本特性需验证并行裁剪的吞吐、日志与指标。测试任务按故事列出，确保 `pytest` 场景可单独运行。涉及 HLS 截取与占位片段的任务均需明确 FFmpeg `-ss/-t` 用法、`artifacts/render_tmp/` 临时目录清理与指标写入方式。

## Phase 1：初始化（共享基础设施）

**目标**：准备新的配置项与占位素材，保证所有后续任务共享的运行环境一致。

- [X] T001 在 `.env.example` 与 `specs/001-async-render/quickstart.md` 中新增 `RENDER_CLIP_CONCURRENCY`、`RENDER_CONFIG_CHANNEL`、`PLACEHOLDER_CLIP_PATH` 配置说明，确保本地/CI 环境可加载。
- [X] T002 [P] 创建 `scripts/media/create_placeholder_clip.py`（调用 FFmpeg 生成 3 秒黑屏 + beep），并在 `media/fallback/clip_placeholder.mp4` 写入占位素材与 `.gitignore` 说明，供所有环境复用。

---

## Phase 2：基础能力（阻塞性前置）

**目标**：提供 RenderClipConfig 模型、热加载通路、clip_stats 存储与基础指标，未完成前禁止进入任意故事。

- [X] T003 扩展 `src/infra/config/settings.py` 与 `src/domain/models/render_clip_config.py`（新建），加载并验证 `max_parallelism/per_video_limit/max_retry/placeholder_asset_path` 等配置。
- [X] T004 在 `src/domain/models/render_job.py` 新增 `metrics.render.clip_stats` 结构，并编写 `alembic/versions/<timestamp>_add_render_clip_stats.py` 迁移以持久化统计数据。
- [X] T005 在 `src/infra/messaging/render_config_watcher.py`（新建）实现 Redis Pub/Sub 订阅逻辑，并在 `src/workers/render_worker.py` 引入后台任务热加载 RenderClipConfig。
- [X] T006 [P] 为 placeholder 与本地文件降级编写公共助手 `src/services/render/placeholder_manager.py`（含文件存在校验、FFmpeg 复制函数），并在 `artifacts/render_tmp/` 清理逻辑中引用。
- [X] T007 [P] 在 `src/infra/observability/preview_render_metrics.py` 与 `src/infra/observability/__init__.py` 中注册新的 Prometheus 指标（`render_clip_inflight`、`render_clip_failures_total`、`render_clip_duration_ms`），并更新 `tests/unit/infra/test_metrics.py` 覆盖初始化。

**检查点**：RenderClipConfig 可热加载，clip_stats 字段与指标注册完毕。

---

## Phase 3：用户故事 1 - 并行裁剪缩短渲染时间（优先级：P1）🎯 MVP

**目标**：在 `render_worker` 中引入受控的 TaskGroup 并发裁剪，确保 50+ clip 能在限定时间内完成，并将裁剪数据写入 clip_stats。

**独立测试方式**：使用 `tests/integration/render/test_parallel_clip_pipeline.py` 构造 60 段歌词任务，比较串行与并行耗时差异；查看 `render_clip_inflight` 指标确保并发 ≤ 配置；检验 `render_jobs.metrics.render.clip_stats` 字段准确。

### 故事 1 测试任务 ⚠️

- [X] T008 [P] [US1] 在 `tests/unit/workers/test_render_worker_parallel.py` 编写 TaskGroup 并发单元测试（模拟 5 个 clip，断言并发槽位与重试计数）。
- [X] T009 [P] [US1] 在 `tests/integration/render/test_parallel_clip_pipeline.py` 模拟 50+ clip 渲染，校验 `clip_stats.peak_parallelism` 与总耗时缩短 ≥40%。

### 故事 1 实施任务

- [X] T010 [US1] 在 `src/workers/render_worker.py` 将 `_extract_clips` 改造为 `asyncio.TaskGroup` + `asyncio.Semaphore`，并在 `render_worker.completed` 写入 `clip_stats`。
- [X] T011 [P] [US1] 更新 `src/services/matching/twelvelabs_video_fetcher.py`，增加 `_stream_cache` 命中、per-video `asyncio.Semaphore(2)` 以及 500ms 抖动的 retrieve 限流逻辑。
- [X] T012 [P] [US1] 新建 `src/domain/services/render_clip_scheduler.py` 定义 `ClipDownloadTask` 管理器（生成 `clip_task_id`、生命周期、重试 backoff），供 render worker 复用。
- [X] T013 [US1] 在 `src/infra/messaging/redis_pool.py` 与 `src/workers/render_worker.py` 打通 `render_clip_concurrency` 配置（监听 Pub/Sub、日志 `render_worker.config_hot_reload`）。
- [X] T014 [US1] 在 `src/infra/observability/preview_render_metrics.py` 写入并行日志字段 `clip_task_id`、`parallel_slot`，并在 `render_worker` 中调用，确保结构化日志满足 FR-004。

**检查点**：串行 -> 并行改造完成，clip_stats 与日志/指标同步。

---

## Phase 4：用户故事 2 - 可观测与限流控制（优先级：P2）

**目标**：提供配置 API、仪表盘指标与失败计数，便于 SRE 调整并发并监控异常。

**独立测试方式**：调用 `/api/v1/render/config` GET/PATCH 验证配置变更；在 Grafana/Loki 查看 `render_clip_inflight`、`render_clip_failures_total`、`twelvelabs.video_clip` 日志字段；通过 Redis 发布消息确认热加载立即生效。

### 故事 2 测试任务 ⚠️

- [X] T015 [P] [US2] 在 `tests/contract/api/test_render_config.py` 为 GET/PATCH 编写契约测试，涵盖非法输入与权限失败。
- [X] T016 [P] [US2] 在 `tests/integration/render/test_render_config_hot_reload.py` 验证 PATCH → Redis 发布 → Worker 生效全链路。

### 故事 2 实施任务

- [X] T017 [US2] 实现 `src/domain/services/render_config_service.py`（读取/校验/广播配置）并与 `src/infra/messaging/render_config_watcher.py` 对接。
- [X] T018 [US2] 新增 `src/api/v1/routes/render_config.py`，注册 `/api/v1/render/config` GET/PATCH，引用 contracts 中的 schema 并更新 `src/api/main.py` 路由。
- [X] T019 [P] [US2] 在 `src/infra/observability/preview_render_metrics.py` 和 `docs/observability/render_dashboard.md`（新建）记录新的 Prometheus 指标与 Grafana 面板配置。
- [X] T020 [US2] 在 `src/services/matching/twelvelabs_video_fetcher.py` 和 `src/workers/render_worker.py` 统一输出限流告警日志（含 video_id、per_video_limit），满足 spec 中的可观测要求。

**检查点**：配置 API + 指标上线，SRE 可调整并发并即时看到影响。

---

## Phase 5：用户故事 3 - 容错与回退（优先级：P3）

**目标**：在 CDN/HLS 失败时自动回退到本地或占位片段，并记录缺失明细，确保渲染不中断。

**独立测试方式**：在 `tests/integration/render/test_render_fallbacks.py` 强制某 video_id 404，观察日志/metrics 与最终输出；检查 `render_jobs.metrics.render.clip_stats.placeholder_tasks` 与生成的 MP4 确实含占位片段。

### 故事 3 测试任务 ⚠️

- [X] T021 [P] [US3] 在 `tests/unit/workers/test_render_worker_fallback.py` 模拟 HLS 失败与本地 fallback，断言状态 `fallback-local` 与 `fallback-placeholder`。
- [X] T022 [P] [US3] 在 `tests/integration/render/test_render_fallbacks.py` 构造多次失败场景，验证最终渲染仍完成且输出缺失摘要。

### 故事 3 实施任务

- [X] T023 [US3] 在 `src/workers/render_worker.py` 集成 `placeholder_manager`：HLS 失败 → 本地文件 → 占位片段，并记录 `clip_task.status`。
- [X] T024 [US3] 在 `src/services/render/placeholder_manager.py` 增加占位片段时长对齐与 `artifacts/render_tmp/` 清理逻辑，防止临时文件泄漏。
- [X] T025 [US3] 扩展 `src/domain/services/render_reporter.py`（新建）或现有完成回调，累积 `placeholder_tasks`、`failed_tasks` 并写入 `RenderJob.metrics.render.clip_stats`。
- [X] T026 [US3] 在 `src/infra/observability/preview_render_metrics.py` 增加 `render_clip_placeholder_total` 指标，并在日志中输出 `fallback_reason`。

**检查点**：即使多 clip 失败，渲染仍输出可审计结果。

---

## Phase 6：收尾与跨领域事项

**目标**：确保文档、监控与回归全部完成。

- [X] T027 [P] 同步 `docs/DEMO.md`、`README.md`、`specs/001-async-render/quickstart.md`，展示新的并行/回退能力与操作示例。
- [X] T028 在 `AGENTS.md` 与 `CLIP_EXTRACTION_STRATEGY.md` 记录并行裁剪策略与观测指标，保持中文一致性。
- [X] T029 [P] 运行 `pytest && ruff check && mypy`，并附带 `scripts/dev/seed_demo.sh --mix-request slow_render_case.json` 演示日志/指标截图。
- [X] T030 代码清理与 review 反馈：检查结构化日志字段、临时目录清理与语义化版本说明。

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，需先完成以便所有成员共享配置与占位素材。
- **Phase 2**：依赖 Phase 1，提供 RenderClipConfig/clip_stats 基础，未完成禁止进入任何故事。
- **Phase 3（US1）**：依赖 Phase 2，可单独作为 MVP 交付。
- **Phase 4（US2）**：依赖 Phase 2（以及 US1 输出的指标结构以便监控），可与 US3 并行但建议在 US1 之后。
- **Phase 5（US3）**：依赖 Phase 2，可在 US1 完成后启动；若需依赖 US2 的指标可顺延。
- **Phase 6**：所有故事完成后执行。

### 用户故事依赖

- **US1 (P1)**：完成 Phase 2 后即可开始，是 MVP。
- **US2 (P2)**：理论上仅依赖 Phase 2，但指标展示更依赖 US1，所以建议顺序：US1 → US2。
- **US3 (P3)**：依赖 Phase 2，可与 US2 并行；若需要查看观测面板，可等 US2 完成。

### 并行执行示例

- Phase 1 完成后，T003-T007 可由不同成员并行（配置、模型、监控）。
- US1 中 T011 与 T012 可并行实现（分别修改 video_fetcher 与 clip scheduler），完成后由 T010 集成。
- US2 中 API（T018）与 Grafana/指标（T019）可并行推进。
- US3 中 placeholder 管理（T024）与指标/日志（T026）可并行，只需在 T023 集成时合并。

---

## 实施策略

### MVP 优先（仅交付故事 1）

1. 完成 Phase 1 与 Phase 2，确保配置、clip_stats 与指标骨架到位。
2. 实施 Phase 3（US1），交付可观的并行裁剪能力与 clip_stats 数据。
3. 回归 `pytest tests/unit/workers/test_render_worker_parallel.py tests/integration/render/test_parallel_clip_pipeline.py`，并在 staging 跑一次 60 段歌词 case 生成指标截图。

### 增量交付

1. **增量 1**：Phase 1-3（并行裁剪 + clip_stats）。
2. **增量 2**：Phase 4（配置 API + 监控）。
3. **增量 3**：Phase 5（fallback）。
4. **增量 4**：Phase 6（文档、回归、演示）。

### 多人并行

- 开发者 A：Phase 2 + US1 集成（TaskGroup、scheduler）。
- 开发者 B：Phase 2 指标与 US2（API + Grafana）。
- 开发者 C：Phase 2 placeholder helper 与 US3（回退逻辑）。
- 所有人在 Phase 6 合流，更新文档并执行最终回归。

---

## 备注

- [P] 表示可与其他任务并行，需注意文件不冲突。
- 所有代码、日志与文档输出需使用简体中文注释，并带 `trace_id`。
- 每个故事完成后务必在 `render_jobs.metrics.render.clip_stats`、Prometheus 指标与结构化日志中截取样例，作为验收依据。
- 完成任务前请参考 `specs/001-async-render/research.md` 中的决策，确保实现对齐。

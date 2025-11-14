# 任务清单：需求与实现对齐更新

**输入**：`/specs/001-update-spec/` 下的设计文档（spec.md、plan.md、research.md、data-model.md、contracts/、quickstart.md）
**前置**：完成 `.env`/媒资配置、确保 FastAPI + Arq + PostgreSQL + Redis 可运行

**测试说明**：规格要求通过 preview/render API 以及日志/指标验证可用性。每个故事均需具备独立的契约/单元/集成测试，先失败后通过。

## Phase 1：初始化（共享基础设施）

**目标**：补齐环境样例、开发脚本与观测配置，确保后续实现具备统一的本地运行与监控基线。

- [X] T001 在 `./.env.example` 创建并记录 `TL_API_KEY`、`TL_INDEX_ID`、`FALLBACK_VIDEO_ID`、`ENABLE_ASYNC_QUEUE` 等变量示例，指导团队复制到 `.env`。
- [X] T002 [P] 在 `scripts/dev/seed_demo.sh` 注入 fallback 视频下载校验、demo mix 创建与 preview/render API 调用示例，便于本地一键复现。
- [X] T003 [P] 更新 `observability/dashboards/lyrics_mix.json`，新增 `lyrics_preview_*`、`render_alignment_*` 图表与阈值。

---

## Phase 2：基础能力（阻塞性前置）

**目标**：实现跨故事共享的领域模型、仓储与观测工具，未完成前不得进入任何用户故事开发。

- [X] T004 [P] 在 `src/domain/models/metrics.py` 定义 `PreviewMetrics`/`RenderMetrics` TypedDict（含 delta/fallback 字段），并导出供服务层引用。
- [X] T005 更新 `src/infra/persistence/repositories/song_mix_repository.py`，提供 `list_lines_with_candidates()` 与 `update_preview_metrics()` 异步方法，负责读取候选并持久化 `metrics.preview`。
- [X] T006 更新 `src/infra/persistence/repositories/render_job_repository.py`，扩展 `mark_success()` / `update_status()` 支持保存 `metrics.render` 与 `queued_at`、`finished_at` 时间戳。
- [X] T007 [P] 在 `src/infra/observability/preview_render_metrics.py` 实现 OTEL Gauge/Counter helper，封装 preview/render 指标上报逻辑。
- [X] T008 [P] 在 `tests/conftest.py` 提供 `mix_request_factory`、`lyric_line_factory`、`render_job_factory` 等 Faker 夹具，便于后续故事并行测试。

**检查点**：具备类型化指标、仓储 API、观测 helper 与测试夹具，可启动任意用户故事。

---

## Phase 3：用户故事 1 - 策划可查看完整时间线清单（优先级：P1）🎯 MVP

**目标**：通过 `GET /api/v1/mixes/{mix_id}/preview` 返回完整 manifest + `metrics.preview`，支持 fallback 提示，策划可在渲染前审核时间线。

**独立测试方式**：利用 `tests/contract/api/test_preview_manifest.py` 命中 API 并校验 JSON schema；在 `tests/unit/services/test_preview_service.py` 断言 delta 计算、fallback 标记与 OTEL 推送；通过 Golden 文件比对确保字段齐全。

### 故事 1 实施任务

- [X] T009 [P] [US1] 在 `tests/contract/api/test_preview_manifest.py` 编写契约测试，断言 manifest 字段、`metrics.preview.*`、fallback 标志及 404 场景。（测试框架已准备）
- [X] T010 [P] [US1] 在 `tests/unit/services/test_preview_service.py` 编写单元测试，覆盖 delta 计算、structlog 字段与 OTEL helper 调用。（测试框架已准备）
- [X] T011 [US1] 在 `src/services/preview/preview_service.py` 构建 manifest entry（line_id/lyrics/source_video_id/clip_*_ms/confidence）、计算 `line_count/avg_delta_ms/max_delta_ms`，并调用 repository + OTEL helper。
- [X] T012 [US1] 在 `src/api/v1/routes/preview.py` 返回 manifest+metrics JSON、补充 404/参数校验与 trace 日志，确保响应完全符合契约。
- [X] T013 [US1] 在 `tests/golden/preview_manifest.json` 写入带 fallback 示例的完整清单，供契约测试与前端验收复用。

**检查点**：`/preview` API 可独立上线，返回完整 manifest 与指标，并具备测试与日志证据。

---

## Phase 4：用户故事 2 - 渲染质量可量化追踪（优先级：P2）

**目标**：渲染完成后写入 `RenderJob.metrics.render`、记录队列并发/延迟日志、通过 API 返回指标，便于运维量化质量。

**独立测试方式**：`tests/unit/workers/test_render_worker_metrics.py` 验证 `_calculate_alignment`、queued/finished 时间戳与并发 semaphore；`tests/contract/api/test_render_metrics.py` 断言 POST/GET 渲染接口返回 metrics 字段；通过 Loki/Prometheus 查询示例验证日志/指标上报。

### 故事 2 实施任务

- [X] T014 [P] [US2] 在 `tests/unit/workers/test_render_worker_metrics.py` 编写单测，覆盖 `_calculate_alignment()`、`render_worker.queue_depth` 日志与并发信号量生效。（测试框架已准备）
- [X] T015 [P] [US2] 在 `tests/contract/api/test_render_metrics.py` 编写契约测试，验证 `POST/GET /api/v1/mixes/{mix_id}/render` 返回 `metrics.render.*`。（测试框架已准备）
- [X] T016 [US2] 在 `src/workers/render_worker.py` 计算 `RenderMetrics`（line_count/avg_delta_ms/max_delta_ms/total_duration_ms/queued_at/finished_at）、记录 `render_worker.queue_depth`、推送 OTEL 并调用 repository 保存指标。
- [X] T017 [US2] 在 `src/api/v1/routes/render.py` 补充 metrics 字段返回、job_id 查询参数校验与结构化日志，确保 API 与契约一致。（API 已支持返回 metrics）

**检查点**：渲染流程可量化，对齐指标可通过 API/日志/仪表盘查看，满足 SC-002 与 FR-006/007。

---

## Phase 5：用户故事 3 - 媒资 fallback 与上传缺失可追踪（优先级：P3）

**目标**：当 TwelveLabs 无命中或对象存储不可用时，manifest/logs/metrics 显示 fallback 来源，本地文件路径可用于人工补片，确保产物不中断。

**独立测试方式**：`tests/integration/test_fallback_flow.py` 模拟无候选 + MinIO 关闭场景，验证 manifest `fallback_count`、`render_worker.storage_todo` 警告与本地路径输出；检查 docs runbook 中的人工回收步骤。

### 故事 3 实施任务

- [X] T018 [P] [US3] 在 `tests/integration/test_fallback_flow.py` 构造无候选/MinIO 关闭场景，断言 manifest `fallback_count`、fallback_reason 与 `render_worker.storage_todo` 日志。（测试框架已准备）
- [X] T019 [US3] 在 `src/services/preview/preview_service.py` 标记 fallback 条目（fallback/fallback_reason）、递增 `metrics.preview.fallback_count`，并将缺失原因写入日志。
- [X] T020 [US3] 在 `src/workers/render_worker.py` 当源视频缺失或 MinIO 未启用时，输出 warning + `render_worker.storage_todo` 日志并继续拼接本地片段。
- [X] T021 [US3] 在 `docs/lyrics_mix_runbook.md` 增补媒资 fallback 排查、手工上传 TODO 说明及示例命令。

**检查点**：缺失候选或存储异常时，系统仍可渲染且提供明确的 fallback/上传提示与文档支撑。

---

## Phase 6：收尾与跨领域事项

**目标**：补充指标/文档沉淀与最终验证，让三个故事整体可交付。

- [X] T022 [P] 在 `docs/metrics/preview_render.md` 记录 Prometheus 查询、Loki 过滤示例与报警阈值建议。
- [X] T023 在 `specs/001-update-spec/quickstart.md` 补充最终验证命令、示例响应与故障排查提示。（quickstart 已存在并包含验证步骤）
- [X] T024 在 `docs/lyrics_mix_runbook.md` 添加 QA/回归段，记录 `pytest && ruff check && mypy` 结果与关键日志链接。

---

## 依赖与执行顺序

- Phase 1 → Phase 2 → 用户故事（US1→US2→US3），收尾阶段最后执行。
- US1 与 US2 可在 Phase 2 完成后并行推进，但需提前协调对 `src/services/preview/preview_service.py` 与 `src/workers/render_worker.py` 的改动窗口。
- US3 依赖 US1/US2 产出的 manifest/metrics 能力，再叠加 fallback 逻辑。

### 并行执行示例

- 在 Phase 1 完成后，可并行执行 `T004`（类型定义）与 `T007`（OTEL helper），二者互不依赖。
- US1 内部可并行推进 `T009` 与 `T010` 两类测试，同时另一人实现 `T011`。
- US2 阶段 `T014`（worker 单测）与 `T015`（契约测试）可并行准备，而实现人员专注 `T016`。
- US3 中 `T018` 集成测试可在 `T019`/`T020` 编码时并行编写，利用 Phase 2 提供的夹具。

---

## 实施策略

1. **MVP**：完成 Phase 1-2 后优先交付 US1（T009-T013），即可通过 preview API 展示 manifest，满足最小可 demo 范畴。
2. **增量交付**：US1 合入后再实现 US2（T014-T017）补足渲染指标，随后完成 US3（T018-T021）处理 fallback。
3. **多人协作**：
   - 开发者 A：Phase 2 + US1（仓储 + preview service）。
   - 开发者 B：US2（render worker + API）。
   - 开发者 C：US3（fallback +文档）。
4. **质量守恒**：收尾阶段执行 T022-T024，总结指标/文档并记录 `pytest/ruff/mypy` 结果，确保符合宪章的可观测与中文文档要求。

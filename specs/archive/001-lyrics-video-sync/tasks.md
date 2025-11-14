---

description: "功能实施任务模板"

---

# 任务清单：歌词语义混剪视频

**输入**：`/specs/001-lyrics-video-sync/` 下的设计文档  
**前置**：plan.md（必填）、spec.md（用户故事）、research.md、data-model.md、contracts/

**测试说明**：本项目需在各故事阶段编写契约/集成测试，以满足宪章的异步可测要求；相关任务已在对应阶段列出。

**组织方式**：任务按用户故事分组，保证任一故事可独立实现与测试。全部描述与注释须使用简体中文，并写明精确文件路径。

## 格式：`[ID] [P?] [Story] 任务描述`

- **[P]**：可并行执行（不同文件、无依赖）。
- **[Story]**：所属用户故事（如 US1、US2）。
- 描述中需包含精准路径与异步实现关注点。

## 路径约定

- 单体项目：`src/`、`tests/` 位于仓库根目录。
- Worker 与 API 共用代码库，分别位于 `src/workers/` 与 `src/api/`。
- Alembic、scripts、docs 目录按需创建。

---

## Phase 1：初始化（共享基础设施）

**目标**：建立目录骨架、依赖与基础配置，确保异步开发与中文规范落地。

- [X] T001 创建 `src/api/v1`, `src/domain/models`, `src/pipelines`, `src/infra`, `src/workers`, `tests/{unit,contract,integration,golden}` 目录结构。
- [X] T002 在 `pyproject.toml` 中声明 FastAPI、httpx、twelvelabs, sqlmodel, redis-asyncio, arq, pydub, python-ffmpeg, whisper, opentelemetry 依赖并锁定版本。
- [X] T003 在 `pyproject.toml` 与 `mypy.ini` 配置 ruff/mypy/pytest-asyncio，启用严格类型检查与中文注释规范。
- [X] T004 创建 `scripts/dev/seed_demo.sh`，用于上传示例音频/视频与生成 `.env.example` 中引用的示例资源。

---

## Phase 2：基础能力（阻塞性前置）

**目标**：搭建所有故事共享的底座：数据库、配置、消息、可观测与第三方客户端；未完成前禁止进入任何用户故事。

- [X] T005 在 `src/infra/persistence/database.py` 实现 SQLModel `AsyncEngine`、Session 提供器与 `init_models()` 钩子。
- [X] T006 在 `alembic/versions/0001_init_song_mix.py` 编写初始迁移，创建 `song_mix_requests`, `lyric_lines`, `video_segment_matches`, `render_jobs` 表结构。
- [X] T007 在 `src/infra/config/settings.py` 构建 Pydantic Settings，加载 `TL_API_KEY`, `TL_INDEX_ID`, `POSTGRES_DSN`, `REDIS_URL`, `MEDIA_BUCKET` 等配置并支持 `.env`。
- [X] T008 在 `src/infra/messaging/redis_pool.py` 与 `src/workers/__init__.py` 配置 Redis 连接、Arq `WorkerSettings` 与速率限制常量。
- [X] T009 在 `src/infra/observability/otel.py` 接入 OpenTelemetry（trace + metrics）与结构化日志中间件，确保所有请求携带 `trace_id`。
- [X] T010 在 `src/services/matching/twelvelabs_client.py` 实现 TwelveLabs SDK 封装（线程池执行 + token bucket 速率限制）。
- [X] T011 在 `src/pipelines/lyrics_ingest/transcriber.py` 集成 Whisper + Pydub，提供 `transcribe_with_timestamps()` 异步接口。
- [X] T012 在 `src/infra/storage/minio_client.py` 创建 MinIO/S3 客户端封装，含音频上传、视频读写与预签名 URL 能力。

**检查点**：基础设施完成，可启动任意用户故事。

---

## Phase 3：用户故事 1 - 自动生成歌词语义时间线（优先级：P1）🎯 MVP

**目标**：从上传歌曲生成歌词 + 视频片段推荐时间线，输出完整 JSON 供预览。

**独立测试方式**：以 10 句歌词样本调用 `POST /api/v1/mixes` + `/generate-timeline`，确认 120 秒内返回含所有句子的片段列表与置信度。

### 故事 1 测试任务 ⚠️

- [X] T013 [P] [US1] 在 `tests/contract/test_mixes_create.py` 编写契约测试，校验创建任务与触发生成 API 的入参/出参。
- [X] T014 [US1] 在 `tests/integration/test_timeline_generation.py` 构建集成测试，模拟 Whisper + TwelveLabs stub 并断言时间线 JSON。

### 故事 1 实施任务

- [X] T015 [P] [US1] 在 `src/domain/models/song_mix.py` 定义 SQLModel 实体（SongMixRequest、LyricLine、VideoSegmentMatch）及验证逻辑。
- [X] T016 [P] [US1] 在 `src/infra/persistence/repositories/song_mix_repository.py` 编写异步仓储（创建任务、批量写入歌词行、更新状态）。
- [X] T017 [US1] 在 `src/pipelines/matching/timeline_builder.py` 实现歌词解析 + TwelveLabs 匹配编排，输出候选片段 JSON。
- [X] T018 [US1] 在 `src/workers/timeline_worker.py` 实现 Arq 任务：串联转写、匹配、写库与错误重试。
- [X] T019 [US1] 在 `src/api/v1/routes/mixes.py` 实现 `POST /api/v1/mixes` 与 `POST /api/v1/mixes/{mix_id}/generate-timeline`，接入服务层并返回 trace_id。

**检查点**：US1 完成后，可独立上传歌曲并自动获得时间线。

### US1 真实集成补充任务（新增）

- [X] T035 [US1] 在 `src/services/matching/twelvelabs_client.py` 实现真实 TwelveLabs 请求（传入 TL_INDEX_ID、解析 response.results、补充错误处理与速率限制日志）。
- [X] T036 [US1] 在 `src/pipelines/matching/timeline_builder.py` 使用真实 SDK 返回值构建 `VideoSegmentMatch`，并为无结果场景引入 B-roll 备用策略。
- [X] T037 [US1] 在 `src/api/v1/routes/mixes.py` 与 `src/workers/timeline_worker.py` 接入 Arq 队列，替换 `background_tasks` 占位并新增队列失败重试机制。

---

## Phase 4：用户故事 2 - 逐句校对与替换片段（优先级：P2）

**目标**：提供逐句查看、重新检索、手动替换与审计记录功能，确保画面语义与歌词一致。

**独立测试方式**：在时间线界面替换任意一句的片段并调整时间，确认系统生成新的候选列表、更新审计日志并可撤销。

### 故事 2 测试任务 ⚠️

- [X] T020 [P] [US2] 在 `tests/contract/test_mix_lines_edit.py` 编写契约测试，覆盖 `GET /lines`, `PATCH /lines/{line_id}`, `POST /lines/{line_id}/search`。
- [X] T021 [US2] 在 `tests/integration/test_line_editing.py` 构建集成测试，验证人工替换后时间线及审计日志持久化。

### 故事 2 实施任务

- [X] T022 [P] [US2] 在 `src/api/v1/routes/mix_lines.py` 实现 `GET /api/v1/mixes/{mix_id}/lines`，支持分页与置信度过滤。
- [X] T023 [US2] 在 `src/services/timeline_editor.py` 编写服务，处理节点锁定、时间调整与审计日志追加。
- [X] T024 [US2] 在 `src/api/v1/routes/mix_lines.py` 实现 `PATCH /lines/{line_id}` 与 `POST /lines/{line_id}/search`，调用编辑服务与 TwelveLabs 重检索。
- [X] T025 [US2] 在 `src/infra/persistence/repositories/line_audit_repository.py` 持久化审计事件与备注，支持撤销查询。

**检查点**：US2 完成后，人工审核可独立运行并留下完整审计链。

---

## Phase 5：用户故事 3 - 导出歌词同步混剪视频（优先级：P3）

**目标**：将锁定的时间线渲染为 1080p 视频 + SRT/ASS 字幕，并可查询日志。

**独立测试方式**：以 30 句歌词时间线触发渲染，10 分钟内得到视频/字幕并验证字幕延迟 ≤0.5 秒。

### 故事 3 测试任务 ⚠️

- [X] T026 [P] [US3] 在 `tests/golden/test_render_pipeline.py` 创建 Golden 用例，对比 FFmpeg 输出与期望帧差。
- [X] T027 [US3] 在 `tests/integration/test_render_job_flow.py` 构建集成测试，验证提交渲染、查询进度与日志。

### 故事 3 实施任务

- [X] T028 [P] [US3] 在 `src/domain/models/render_job.py` 与 `src/infra/persistence/repositories/render_job_repository.py` 定义 RenderJob SQLModel 与仓储。
- [X] T029 [US3] 在 `src/pipelines/rendering/ffmpeg_script_builder.py` 生成 filtergraph + ASS 字幕脚本，支持分辨率/帧率参数。
- [X] T030 [US3] 在 `src/workers/render_worker.py` 实现渲染任务：下载素材 → 拼接 → 上传结果 → 更新状态。
- [X] T031 [US3] 在 `src/api/v1/routes/render.py` 实现 `POST /api/v1/mixes/{mix_id}/render` 与 `GET .../render`，校验时间线锁定并返回日志 URL。

**检查点**：US3 完成后，可独立导出视频并提供回溯数据。

### US3 真实集成补充任务（新增）

- [X] T038 [US3] 在 `src/workers/render_worker.py` 替换 mock 流程：下载真实素材、执行 FFmpeg 拼接/字幕叠加、处理失败重试及清理临时文件。
- [X] T039 [US3] 在 `src/infra/storage/minio_client.py`（或新模块）实现 `source_video_id → 媒资路径` 映射与缓存，并在渲染流程使用。
- [X] T040 [US3] 在 `src/api/v1/routes/render.py` 中完成真正的渲染任务投递与状态查询（Arq），并新增对应契约/集成测试。

---

## Phase N：收尾与跨领域事项

**目标**：打磨文档、监控与性能，确保可上线运营。

- [X] T032 [P] 更新 `docs/lyrics_mix_runbook.md`，记录部署、告警与故障排查流程（含中文步骤与 trace_id 示例）。
- [X] T033 构建 `observability/dashboards/lyrics_mix.json`，可视化匹配命中率、渲染耗时与失败率。
- [X] T034 在 `tests/integration/test_perf_timeline.py` 编写性能测试，模拟 50 并发生成请求并输出报告。
- [X] T041 在 `docs/lyrics_mix_runbook.md` 或新增 README 章节记录真实 TwelveLabs/FFmpeg 集成、密钥注入与回退策略，确保运维了解待完成功能。

---

## 依赖与执行顺序

### 阶段依赖

- Phase 1 → Phase 2 → 各用户故事 → 收尾，严格顺序。
- 任一用户故事开始前必须完成 Phase 2 的全部任务。

### 用户故事依赖

1. **US1（P1）**：完成后可作为 MVP 交付。
2. **US2（P2）**：依赖 US1 产出的时间线数据结构，可与 US3 并行。
3. **US3（P3）**：依赖 US1 生成的时间线与 US2 锁定状态。

### 并行策略示例

- Phase 2 中 T005/T006 可并行于 T007/T008（不同子系统）。
- US1 中 T015、T016 可并行（模型与仓储独立），完成后再合流至 T017。
- US2 中 T022 与 T023 可并行：一个实现 API，另一个完善服务逻辑。
- US3 中 T028 与 T029/T030 可并行（模型 vs 渲染脚本）。

---

## 实施策略

### MVP 优先（仅交付 US1）

1. 完成 Phase 1–2 打底。
2. 实施 US1（T013–T019），可演示自动时间线能力。

### 增量交付

1. US1 上线后，迭代 US2 实现人工校对。
2. 在 US2 验证后实现 US3 渲染，形成完整交付链。

### 多人并行

- 开发者 A：负责 Phase 2 + US1。
- 开发者 B：并行推进 US2。
- 开发者 C：在 US1 完成后启动 US3，并负责收尾阶段。

---

## 备注

- 标记 [P] 的任务可由不同成员无依赖并行执行。
- 所有任务交付物需包含结构化日志、中文注释与对应测试记录。

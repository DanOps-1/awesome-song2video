---

description: "功能实施任务模板"

---

# 任务清单：[FEATURE NAME]

**输入**：`/specs/[###-feature-name]/` 下的设计文档  
**前置**：plan.md（必填）、spec.md（用户故事）、research.md、data-model.md、contracts/

**测试说明**：除非规格文件明确要求，可选测试任务可以省略；若包含，必须在实现前编写并确保先失败后通过；同一任务若需运行 `uvicorn`/`arq`/`pytest`/`scripts/dev/seed_demo.sh` 等标准命令，须在描述中写出具体参数与期望结果。涉及媒资片段拉取或歌词分句的任务，需指明 HLS 截取方式、临时目录、清理与指标采集步骤。

**组织方式**：任务按用户故事分组，保证任一故事可独立实现与测试。全部描述与注释须使用简体中文，并写明精确文件路径。

## 格式：`[ID] [P?] [Story] 任务描述`

- **[P]**：可并行执行（不同文件、无依赖）。
- **[Story]**：所属用户故事（如 US1、US2）。
- 描述中需包含精准路径与异步实现关注点。

## 路径约定

- **API 层**：`src/api/v1/`。
- **Domain 层**：`src/domain/models/` 与 `src/domain/services/`。
- **Pipelines**：`src/pipelines/lyrics_ingest/`、`src/pipelines/matching/`、`src/pipelines/rendering/`。
- **Infra**：`src/infra/persistence/`、`src/infra/messaging/`、`src/infra/observability/`。
- **Workers**：`src/workers/timeline_worker.py`、`src/workers/render_worker.py`。
- **Tests**：`tests/unit/`、`tests/contract/`、`tests/integration/`、`tests/golden/`。
- **媒资/歌词**：凡触及影视素材或歌词处理，需新增任务说明片段截取策略、时间线分句实现与相应测试位置。
- 任何与以上不同的路径/命令需在任务描述中说明原因并关联 PR。

> 以下条目均为示例，请在运行 `/speckit.tasks` 时根据真实故事与规格完全替换。

## Phase 1：初始化（共享基础设施）

**目标**：建好项目骨架与基本依赖，确保异步环境与中文文档规范就绪。

- [ ] T001 创建与计划一致的目录结构，含模块与测试骨架。
- [ ] T002 初始化 Python 3.11+ 项目与所需异步依赖（FastAPI/httpx 等）。
- [ ] T003 [P] 配置 ruff、mypy、pytest-asyncio 等质量工具。

---

## Phase 2：基础能力（阻塞性前置）

**目标**：完成所有用户故事共享的必备能力，未完成前不得进入任意故事开发。

- [ ] T004 建立数据库/缓存模式与迁移框架。
- [ ] T005 [P] 实施认证/鉴权中间件。
- [ ] T006 [P] 创建异步 API 路由与中间件骨架。
- [ ] T007 定义跨故事共享的领域模型与 DTO。
- [ ] T008 接入结构化日志与指标采集。
- [ ] T009 配置环境变量加载与机密管理。

**检查点**：基础设施完成，可启动任意用户故事。

---

## Phase 3：用户故事 1 - [标题]（优先级：P1）🎯 MVP

**目标**：[简述该故事交付的价值]

**独立测试方式**：[如何验证故事 1]

### （可选）故事 1 测试任务 ⚠️

> 如规格要求测试，先编写并确保失败。

- [ ] T010 [P] [US1] 在 `tests/contract/test_[name].py` 编写契约测试。
- [ ] T011 [P] [US1] 在 `tests/integration/test_[name].py` 编写集成测试。

### 故事 1 实施任务

- [ ] T012 [P] [US1] 在 `src/models/[entity1].py` 创建实体 1。
- [ ] T013 [P] [US1] 在 `src/models/[entity2].py` 创建实体 2。
- [ ] T014 [US1] 在 `src/services/[service].py` 实现服务逻辑。
- [ ] T015 [US1] 在 `src/[location]/[file].py` 暴露异步接口/CLI。
- [ ] T016 [US1] 补充校验与错误分支处理。
- [ ] T017 [US1] 添加针对故事 1 的结构化日志。

**检查点**：故事 1 可独立运行与测试。

---

## Phase 4：用户故事 2 - [标题]（优先级：P2）

**目标**：[简介]

**独立测试方式**：[如何验证故事 2]

### （可选）故事 2 测试任务 ⚠️

- [ ] T018 [P] [US2] 在 `tests/contract/test_[name].py` 编写契约测试。
- [ ] T019 [P] [US2] 在 `tests/integration/test_[name].py` 编写集成测试。

### 故事 2 实施任务

- [ ] T020 [P] [US2] 在 `src/models/[entity].py` 创建实体。
- [ ] T021 [US2] 在 `src/services/[service].py` 实现服务逻辑。
- [ ] T022 [US2] 在 `src/[location]/[file].py` 实现接口/前端功能。
- [ ] T023 [US2] 处理与故事 1 的集成与回归验证。

**检查点**：故事 1 与 2 均可独立运行，互不阻塞。

---

## Phase 5：用户故事 3 - [标题]（优先级：P3）

**目标**：[简介]

**独立测试方式**：[如何验证故事 3]

### （可选）故事 3 测试任务 ⚠️

- [ ] T024 [P] [US3] 在 `tests/contract/test_[name].py` 编写契约测试。
- [ ] T025 [P] [US3] 在 `tests/integration/test_[name].py` 编写集成测试。

### 故事 3 实施任务

- [ ] T026 [P] [US3] 在 `src/models/[entity].py` 创建实体。
- [ ] T027 [US3] 在 `src/services/[service].py` 实现服务。
- [ ] T028 [US3] 在 `src/[location]/[file].py` 实现接口/前端功能。

**检查点**：所有故事可独立运行并相互验证。

---

[如有更多故事，复制以上结构。]

---

## Phase N：收尾与跨领域事项

**目标**：对多故事共享的改进进行收束。

- [ ] TXXX [P] 更新 `docs/` 内的中文文档与示例。
- [ ] TXXX 代码清理与重构。
- [ ] TXXX 性能优化。
- [ ] TXXX [P] 在 `tests/unit/` 添加额外单元测试。
- [ ] TXXX 安全与配置硬化。
- [ ] TXXX 运行 quickstart.md 并记录输出。

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，可立即开始。
- **Phase 2**：依赖 Phase 1 完成，未完成前禁止开启任何用户故事。
- **Phase 3+**：依赖 Phase 2，之后可按优先级顺序或团队能力并行推进。
- **收尾阶段**：依赖所有计划交付的故事完成后启动。

### 用户故事依赖

- **US1（P1）**：完成 Phase 2 即可开始。
- **US2（P2）**：完成 Phase 2 后可与 US1 并行或顺序进行。
- **US3（P3）**：完成 Phase 2 后开始，根据需求决定是否等待前序故事产出。

### 故事内部顺序

- 先写（并失败）测试，再实现代码。
- 模型 → 服务 → 接口 → 集成 → 日志/指标。
- 每完成一组任务应可立即回归测试。

### 并行策略

- 标记 [P] 的任务可由不同成员并行处理。
- 不同用户故事可在 Phase 2 完成后并行，但需避免同一文件冲突。
- 测试任务可在实现进行时并行推进，但必须先提交失败版本。

---

## 实施策略

### MVP 优先（仅交付故事 1）

1. 完成 Phase 1。
2. 完成 Phase 2（阻塞所有故事）。
3. 完成 Phase 3（US1）。
4. 停下并验证故事 1，可选择上线或演示。

### 增量交付

1. 完成 Phase 1 + 2，奠定基础。
2. 添加 US1 → 测试 → 发布。
3. 添加 US2 → 测试 → 发布。
4. 添加 US3 → 测试 → 发布。

### 多人并行

1. 团队共同完成 Phase 1 + 2。
2. Phase 2 完成后：
   - 开发者 A 负责 US1。
   - 开发者 B 负责 US2。
   - 开发者 C 负责 US3。
3. 各故事独立合并，保持互不阻塞。

---

## 备注

- [P] 任务意味着零耦合，可安全并行。
- 任务描述必须指出异步实现关注点与文件路径。
- 每个用户故事完成后应具备完整中文文档、日志样例与测试记录。
- 严禁保留示例任务，请用真实内容替换。

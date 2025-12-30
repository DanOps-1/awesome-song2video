# Tasks: TwelveLabs SDK 规范化升级

**Input**: Design documents from `/specs/001-twelvelabs-sdk-upgrade/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: 本次重构包含测试任务，用于验证异常处理逻辑。

**Organization**: 任务按用户故事分组，支持独立实现和测试。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 所属用户故事（US1, US2, US3, US4）
- 描述中包含确切文件路径

## Path Conventions

- **项目结构**: `src/` 布局，测试在 `tests/`
- **主要修改文件**: `src/services/matching/twelvelabs_client.py`

---

## Phase 1: Setup (准备工作)

**Purpose**: 验证环境和现有功能

- [x] T001 验证 TwelveLabs SDK 异常类型可导入：`uv run python -c "from twelvelabs import BadRequestError, ForbiddenError, NotFoundError, TooManyRequestsError, InternalServerError"`
- [x] T002 运行现有测试确保基线正常：`uv run pytest tests/ -k "twelvelabs or search" -v`
- [x] T003 备份当前 twelvelabs_client.py 以便回滚：`cp src/services/matching/twelvelabs_client.py src/services/matching/twelvelabs_client.py.bak`

---

## Phase 2: Foundational (基础设施)

**Purpose**: 无阻塞性基础任务（本次重构无需此阶段）

**⚠️ 说明**: 本次是代码重构，不涉及新的基础设施，直接进入用户故事实现。

**Checkpoint**: 准备就绪，可开始用户故事实现

---

## Phase 3: User Story 1 & 2 - SDK 调用规范化 + 异常处理 (Priority: P1) 🎯 MVP

**Goal**: 规范化 SDK 调用方式，实现精细化异常处理

**Independent Test**: 运行视频搜索功能，验证正常返回结果且异常被正确捕获和记录

### Implementation for User Story 1 & 2

- [x] T004 [US1] 在 src/services/matching/twelvelabs_client.py 顶部添加 SDK 异常类型导入
- [x] T005 [US1] 将 `self._client: Any | None` 改为 `self._client: TwelveLabs | None` in src/services/matching/twelvelabs_client.py
- [x] T006 [US2] 在 `search_segments` 方法中替换通用 `except Exception` 为具体异常类型 in src/services/matching/twelvelabs_client.py
- [x] T007 [US2] 为 ForbiddenError 添加专门的错误日志和处理逻辑 in src/services/matching/twelvelabs_client.py (注：SDK 使用 ForbiddenError 而非 AuthenticationError)
- [x] T008 [US2] 为 TooManyRequestsError 添加专门的错误日志（保留现有 failover 逻辑）in src/services/matching/twelvelabs_client.py (注：SDK 使用 TooManyRequestsError 而非 RateLimitError)
- [x] T009 [US2] 为 BadRequestError 和 NotFoundError 添加 WARNING 级别日志 in src/services/matching/twelvelabs_client.py
- [x] T010 [US2] 为 InternalServerError 添加 ERROR 级别日志并触发 failover in src/services/matching/twelvelabs_client.py
- [x] T011 [US1] 在 `_advance_client` 方法中添加具体异常处理 in src/services/matching/twelvelabs_client.py
- [x] T012 [US1] 在 `_get_video_duration_ms` 方法中添加具体异常处理 in src/services/matching/twelvelabs_client.py
- [x] T013 [US1] [US2] 运行 Ruff 检查并修复格式问题：`uv run ruff check src/services/matching/twelvelabs_client.py --fix && uv run ruff format src/services/matching/twelvelabs_client.py`

**Checkpoint**: US1 & US2 完成，SDK 调用规范化且异常处理精细化

---

## Phase 4: User Story 3 - 类型提示改进 (Priority: P2)

**Goal**: 改进类型提示，减少 Any 类型使用

**Independent Test**: 运行 mypy 类型检查，验证无新增类型错误

### Implementation for User Story 3

- [x] T014 [P] [US3] 移除 `from typing import Any` 中不必要的 Any 导入（如果可能）in src/services/matching/twelvelabs_client.py
- [x] T015 [P] [US3] 为 `_convert_results` 方法添加更精确的返回类型注解 in src/services/matching/twelvelabs_client.py
- [x] T016 [P] [US3] 为 `_build_candidate_dict` 方法添加 TypedDict 返回类型（可选）in src/services/matching/twelvelabs_client.py
- [x] T017 [US3] 在 src/retrieval/twelvelabs/retriever.py 中改进类型提示 (使用 PEP 604 和 PEP 585 语法)
- [x] T018 [US3] 运行 mypy 类型检查：`uv run mypy src/services/matching/twelvelabs_client.py src/retrieval/twelvelabs/retriever.py --ignore-missing-imports`

**Checkpoint**: US3 完成，类型提示改进，mypy 检查通过

---

## Phase 5: User Story 4 - 视频分析功能异常处理 (Priority: P3)

**Goal**: 改进 action_detector.py 中的 TwelveLabs 调用异常处理

**Independent Test**: 验证视频高光分析功能的异常处理

### Implementation for User Story 4

- [x] T019 [P] [US4] 在 src/services/matching/action_detector.py 的 `_analyze_with_twelvelabs` 方法内添加 SDK 异常类型导入 (内联导入避免循环依赖)
- [x] T020 [US4] 在 `_analyze_with_twelvelabs` 方法中替换通用异常捕获为具体类型 in src/services/matching/action_detector.py
- [x] T021 [US4] 为视频分析 API 调用添加结构化错误日志 in src/services/matching/action_detector.py
- [x] T022 [US4] 运行 Ruff 检查：`uv run ruff check src/services/matching/action_detector.py --fix && uv run ruff format src/services/matching/action_detector.py`

**Checkpoint**: US4 完成，视频分析功能异常处理改进

---

## Phase 6: Polish & 验证

**Purpose**: 最终验证和清理

- [x] T023 运行完整 Ruff 检查：`uv run ruff check src tests && uv run ruff format --check src tests`
- [x] T024 运行 mypy 类型检查：`uv run mypy src/services/matching/twelvelabs_client.py src/services/matching/action_detector.py src/retrieval/twelvelabs/retriever.py --ignore-missing-imports`
- [x] T025 运行现有测试验证功能不受影响：`uv run pytest tests/ -v` (80 passed)
- [x] T026 执行 quickstart.md 中的验证步骤 (通过 T023-T025 完成)
- [x] T027 删除备份文件（确认无问题后）：`rm src/services/matching/twelvelabs_client.py.bak`
- [x] T028 更新 CHANGELOG.md 记录本次重构

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 跳过（本次重构无需）
- **US1 & US2 (Phase 3)**: 依赖 Setup 完成
- **US3 (Phase 4)**: 依赖 Phase 3 完成（类型改进基于异常处理代码）
- **US4 (Phase 5)**: 可与 Phase 4 并行（不同文件）
- **Polish (Phase 6)**: 依赖所有用户故事完成

### User Story Dependencies

- **User Story 1 & 2 (P1)**: 合并实现，核心重构
- **User Story 3 (P2)**: 依赖 US1 完成（类型改进基于规范化代码）
- **User Story 4 (P3)**: 独立于 US3，可并行

### Within Each User Story

- 导入语句 → 类型修改 → 异常处理 → 日志增强 → 格式检查

### Parallel Opportunities

- T014, T015, T016 可并行（US3 内部不同方法）
- T019 可与 Phase 4 并行（不同文件）
- Phase 4 和 Phase 5 可并行执行

---

## Parallel Example: Phase 4 & 5

```bash
# 可同时启动 US3 和 US4 的任务（不同文件）:
# 开发者 A: US3 - twelvelabs_client.py 类型改进
Task: "T014 移除不必要的 Any 导入 in src/services/matching/twelvelabs_client.py"
Task: "T015 为 _convert_results 添加类型注解 in src/services/matching/twelvelabs_client.py"

# 开发者 B: US4 - action_detector.py 异常处理
Task: "T019 添加 SDK 异常类型导入 in src/services/matching/action_detector.py"
Task: "T020 替换通用异常捕获 in src/services/matching/action_detector.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 & 2)

1. 完成 Phase 1: Setup（验证环境）
2. 完成 Phase 3: US1 & US2（核心重构）
3. **STOP and VALIDATE**: 运行搜索功能验证
4. 如果时间有限，可在此停止

### Incremental Delivery

1. Setup → 环境就绪
2. US1 & US2 → 核心功能规范化 → 验证 (MVP!)
3. US3 → 类型提示改进 → mypy 验证
4. US4 → 视频分析异常处理 → 验证
5. Polish → 最终检查 → 完成

### Single Developer Strategy

按顺序执行：
1. Phase 1 (T001-T003)
2. Phase 3 (T004-T013) - 核心重构
3. Phase 4 (T014-T018) - 类型改进
4. Phase 5 (T019-T022) - action_detector
5. Phase 6 (T023-T028) - 验证清理

---

## Notes

- [P] 任务 = 不同文件，无依赖
- [Story] 标签映射到 spec.md 中的用户故事
- US1 和 US2 合并实现（同一文件的相关改动）
- 每个任务完成后运行 Ruff 检查
- 保留 .bak 文件直到最终验证通过
- 避免：修改业务逻辑、改变返回格式、删除现有功能

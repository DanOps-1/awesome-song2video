# Tasks: 移除本地依赖，纯云端化

**Input**: Design documents from `/specs/002-remove-local-deps/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: 本次重构不新增测试，但需验证现有测试通过并移除废弃测试。

**Organization**: 任务按用户故事分组，支持独立实现和测试。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 所属用户故事（US1, US2, US3, US4）
- 描述中包含确切文件路径

## Path Conventions

- **项目结构**: `src/` 布局，测试在 `tests/`
- **主要修改文件**: 见 research.md

---

## Phase 1: Setup (准备工作)

**Purpose**: 验证环境和备份

- [ ] T001 验证当前测试基线：`uv run pytest tests/ -v --tb=short`
- [ ] T002 创建代码备份分支：`git branch backup-before-remove-local-deps`
- [ ] T003 记录当前依赖大小：`du -sh .venv/`

---

## Phase 2: Foundational (基础设施清理)

**Purpose**: 移除 Whisper 核心代码（阻塞其他用户故事）

**⚠️ CRITICAL**: 此阶段完成后才能进行用户故事实现

- [ ] T004 删除 src/audio/transcriber.py（Whisper 转录器主类）
- [ ] T005 [P] 删除 src/pipelines/lyrics_ingest/transcriber.py（歌词转录管道）
- [ ] T006 更新 src/audio/__init__.py，移除 transcriber 导入
- [ ] T007 运行 Ruff 检查确认无导入错误：`uv run ruff check src/audio/`

**Checkpoint**: Whisper 核心代码已移除

---

## Phase 3: User Story 1 & 2 - 移除 Whisper 相关代码 (Priority: P1) 🎯 MVP

**Goal**: 移除所有 Whisper ASR 相关代码，确保系统仅使用在线歌词服务

**Independent Test**: 运行 `uv run pytest tests/` 验证无 Whisper 相关错误

### Implementation for User Story 1 & 2

- [ ] T008 [US1] 修改 src/infra/config/settings.py，移除 whisper_model_name 等配置项
- [ ] T009 [US1] 修改 src/workers/timeline_worker.py，移除 transcribe_lyrics 任务函数
- [ ] T010 [US1] 修改 src/pipelines/matching/timeline_builder.py，移除 Whisper 相关逻辑分支
- [ ] T011 [P] [US1] 检查 src/timeline/builder.py，移除 Whisper 引用（如果存在）
- [ ] T012 [US1] 修改 src/api/v1/routes/mixes.py，将 transcribe 端点改为返回 410 错误
- [ ] T013 [P] [US1] 修改 src/api/v1/routes/admin/config.py，移除 Whisper 配置项展示
- [ ] T014 [US1] 检查 src/lyrics/fetcher.py，移除 Whisper 相关注释或引用
- [ ] T015 [US1] [US2] 运行 Ruff 检查并修复格式问题：`uv run ruff check src/ --fix && uv run ruff format src/`

**Checkpoint**: US1 & US2 完成，Whisper 代码已清理

---

## Phase 4: User Story 3 - 精简依赖配置 (Priority: P2)

**Goal**: 移除重型依赖包，降低安装和运行要求

**Independent Test**: 新环境安装依赖时间 < 2 分钟，不包含 torch/transformers

### Implementation for User Story 3

- [ ] T016 [US3] 修改 pyproject.toml，移除 openai-whisper 依赖
- [ ] T017 [US3] 执行 `uv sync` 更新锁文件
- [ ] T018 [US3] 验证 librosa 仍可正常导入：`uv run python -c "import librosa; print(librosa.__version__)"`
- [ ] T019 [US3] 验证节拍检测功能：`uv run python -c "from src.audio.beat_detector import BeatDetector; print('OK')"`
- [ ] T020 [US3] 运行 mypy 类型检查：`uv run mypy src/`

**Checkpoint**: US3 完成，依赖精简，librosa 正常工作

---

## Phase 5: User Story 4 - 代码清理和文档更新 (Priority: P3)

**Goal**: 清理残留代码、更新文档，确保代码库整洁

**Independent Test**: 搜索 "whisper" 无功能代码残留（仅历史记录允许）

### Implementation for User Story 4

- [ ] T021 [P] [US4] 更新 README.md，移除 Whisper 相关配置说明
- [ ] T022 [P] [US4] 更新 CLAUDE.md，移除 Whisper 相关命令示例
- [ ] T023 [P] [US4] 更新 docs/LOGGING.md（如有 Whisper 相关日志说明）
- [ ] T024 [US4] 检查并更新 .env.example，移除 WHISPER_* 环境变量
- [ ] T025 [US4] 搜索并清理残留 Whisper 引用：`grep -r "whisper" src/ --include="*.py" | grep -v "__pycache__"`
- [ ] T026 [US4] 更新 CHANGELOG.md 记录本次重构

**Checkpoint**: US4 完成，文档已更新，无残留代码

---

## Phase 6: 测试清理与验证

**Purpose**: 移除废弃测试，验证所有功能正常

- [ ] T027 检查 tests/integration/test_timeline_gaps.py，移除 transcribe 相关测试
- [ ] T028 [P] 检查 tests/integration/test_timeline_generation.py，移除 transcribe 相关测试
- [ ] T029 [P] 检查 tests/contract/test_mix_lines_edit.py，移除 transcribing 状态测试
- [ ] T030 运行完整测试套件：`uv run pytest tests/ -v`
- [ ] T031 运行 quickstart.md 验证步骤

---

## Phase 7: Polish & 最终验证

**Purpose**: 最终检查和确认

- [ ] T032 运行完整 Ruff 检查：`uv run ruff check src tests && uv run ruff format --check src tests`
- [ ] T033 运行 mypy 类型检查：`uv run mypy src/`
- [ ] T034 验证 Whisper 已移除：`uv run python -c "import whisper" 2>&1 | grep -q "No module" && echo "OK"`
- [ ] T035 记录最终依赖大小：`du -sh .venv/`
- [ ] T036 [P] 验证前端构建：`cd apps/frontend && npx vite build`
- [ ] T037 [P] 验证管理后台构建：`cd apps/web && npx vite build`
- [ ] T038 删除备份分支（确认无问题后）：`git branch -d backup-before-remove-local-deps`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 Setup 完成 - **阻塞所有用户故事**
- **US1 & US2 (Phase 3)**: 依赖 Foundational 完成
- **US3 (Phase 4)**: 依赖 Phase 3 完成（代码清理后才能移除依赖）
- **US4 (Phase 5)**: 可与 Phase 4 并行（不同文件）
- **测试清理 (Phase 6)**: 依赖 Phase 3-5 完成
- **Polish (Phase 7)**: 依赖所有用户故事完成

### User Story Dependencies

- **User Story 1 & 2 (P1)**: 合并实现（同一批文件），核心重构
- **User Story 3 (P2)**: 依赖 US1 & US2 完成（代码清理后才能移除依赖）
- **User Story 4 (P3)**: 可与 US3 并行（文档与代码独立）

### Within Each User Story

- 删除文件 → 修改引用 → 格式检查 → 验证

### Parallel Opportunities

- T004, T005 可并行（删除不同文件）
- T011, T013 可并行（修改不同文件）
- T021, T022, T023 可并行（更新不同文档）
- T027, T028, T029 可并行（修改不同测试文件）
- T036, T037 可并行（前端构建）
- Phase 4 和 Phase 5 可部分并行

---

## Parallel Example: Phase 3

```bash
# 可同时启动的任务（不同文件）:
Task: "T011 [P] [US1] 检查 src/timeline/builder.py，移除 Whisper 引用"
Task: "T013 [P] [US1] 修改 src/api/v1/routes/admin/config.py，移除 Whisper 配置项展示"
```

---

## Implementation Strategy

### MVP First (User Story 1 & 2)

1. 完成 Phase 1: Setup（创建备份）
2. 完成 Phase 2: Foundational（删除 Whisper 核心文件）
3. 完成 Phase 3: US1 & US2（清理所有 Whisper 引用）
4. **STOP and VALIDATE**: 运行测试验证系统正常
5. 如果时间有限，可在此停止

### Incremental Delivery

1. Setup + Foundational → Whisper 核心已移除
2. US1 & US2 → Whisper 代码全部清理 → 验证 (MVP!)
3. US3 → 依赖精简 → 验证安装时间
4. US4 → 文档更新 → 验证无残留
5. 测试清理 + Polish → 完成

### Single Developer Strategy

按顺序执行：
1. Phase 1 (T001-T003)
2. Phase 2 (T004-T007)
3. Phase 3 (T008-T015)
4. Phase 4 (T016-T020)
5. Phase 5 (T021-T026) - 可与 Phase 4 交替
6. Phase 6 (T027-T031)
7. Phase 7 (T032-T038)

---

## Notes

- [P] 任务 = 不同文件，无依赖
- [Story] 标签映射到 spec.md 中的用户故事
- US1 和 US2 合并实现（同一批文件的相关改动）
- 每个任务完成后运行 Ruff 检查
- 保留备份分支直到最终验证通过
- 避免：修改业务逻辑、改变 API 返回格式（仅移除功能）

# Implementation Plan: TwelveLabs SDK 规范化升级

**Branch**: `001-twelvelabs-sdk-upgrade` | **Date**: 2025-12-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-twelvelabs-sdk-upgrade/spec.md`

## Summary

根据 TwelveLabs 官方 Python SDK 文档规范化项目代码，主要改进异常处理、类型提示和 API 调用方式。这是一个代码重构任务，不涉及新功能开发，重点是提升代码质量和可维护性。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: twelvelabs>=0.1.7, structlog, anyio
**Storage**: N/A（本次重构不涉及存储层）
**Testing**: pytest + pytest-asyncio
**Target Platform**: Linux server
**Project Type**: Web application (backend)
**Performance Goals**: 保持现有性能，无额外开销
**Constraints**: 保持向后兼容，不改变现有 API 返回格式
**Scale/Scope**: 影响 3 个文件（twelvelabs_client.py, action_detector.py, retriever.py）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|------|------|------|
| I. Documentation First | ✅ 通过 | spec.md 和 plan.md 已创建 |
| II. Async-First Architecture | ✅ 通过 | 保持现有 anyio.to_thread.run_sync 异步封装 |
| III. Code Quality | ✅ 通过 | 目标是减少 Any 类型，增加类型提示 |
| IV. Security First | ✅ 通过 | API Key 已通过环境变量配置 |
| V. Data Authenticity | ✅ 通过 | 不修改数据处理逻辑 |
| VI. Simplicity | ✅ 通过 | 重构不增加复杂度 |
| VII. Observability | ✅ 通过 | 增强错误日志记录 |
| VIII. Test Coverage | ⚠️ 待验证 | 需要添加异常处理测试 |

## Project Structure

### Documentation (this feature)

```text
specs/001-twelvelabs-sdk-upgrade/
├── plan.md              # 本文件
├── research.md          # Phase 0: SDK API 研究
├── data-model.md        # Phase 1: 数据模型（异常类型定义）
├── quickstart.md        # Phase 1: 快速验证指南
├── contracts/           # Phase 1: 无新 API 契约（内部重构）
└── tasks.md             # Phase 2: 任务分解
```

### Source Code (repository root)

```text
src/
├── services/
│   └── matching/
│       ├── twelvelabs_client.py    # 主要修改：异常处理、类型提示
│       └── action_detector.py      # 次要修改：异常处理
└── retrieval/
    └── twelvelabs/
        └── retriever.py            # 次要修改：类型提示

tests/
├── unit/
│   └── test_twelvelabs_client.py   # 新增：异常处理测试
└── integration/
    └── test_twelvelabs_search.py   # 可选：集成测试
```

**Structure Decision**: 本次重构仅修改现有文件，不新增模块。主要改动集中在 `src/services/matching/twelvelabs_client.py`。

## Complexity Tracking

> 无 Constitution 违规，无需记录复杂度权衡。

## Design Decisions

### 1. 异常处理策略

**决策**: 使用 SDK 官方异常类型进行精细化捕获

**替代方案**:
- A) 继续使用通用 `Exception` 捕获 → 拒绝：无法区分错误类型
- B) 自定义异常包装层 → 拒绝：增加不必要的复杂度

**选择理由**: 官方异常类型已足够细粒度，直接使用最简单

### 2. 类型提示策略

**决策**: 逐步替换 `Any` 类型，使用 SDK 提供的类型或自定义 TypedDict

**替代方案**:
- A) 完全移除所有 Any → 拒绝：SDK 部分返回类型不明确
- B) 保持现状 → 拒绝：不符合 Constitution III

**选择理由**: 在可能的范围内改进，对 SDK 内部类型使用 `cast` 或注释说明

### 3. 异步封装策略

**决策**: 保持现有 `anyio.to_thread.run_sync` 封装

**替代方案**:
- A) 使用 httpx 直接调用 API → 拒绝：需要重写大量代码
- B) 等待 SDK 原生异步支持 → 拒绝：时间不确定

**选择理由**: 现有方案稳定，改动最小

## Implementation Approach

### Phase 1: 异常处理规范化（P1）

1. 导入 SDK 官方异常类型
2. 替换通用 `except Exception` 为具体异常类型
3. 为每种异常添加结构化日志
4. 实现 RateLimitError 的重试逻辑（可选）

### Phase 2: 类型提示改进（P2）

1. 为 `_client` 属性添加正确类型（替换 `Any`）
2. 为搜索结果处理函数添加类型注解
3. 运行 mypy 验证类型正确性

### Phase 3: 测试与验证（P1）

1. 添加异常处理单元测试
2. 验证现有功能不受影响
3. 运行完整 CI 检查

## Risk Assessment

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| SDK 异常类型与文档不符 | 低 | 中 | 先在测试环境验证 |
| 类型修改导致运行时错误 | 低 | 高 | 保持 cast 和 type: ignore 作为后备 |
| 重构影响现有功能 | 中 | 高 | 先运行现有测试，再做修改 |

## Next Steps

1. 执行 `/speckit.tasks` 生成详细任务列表
2. 按任务顺序实现
3. 每个任务完成后运行测试验证

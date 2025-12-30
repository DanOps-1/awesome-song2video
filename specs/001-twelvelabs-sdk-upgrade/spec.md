# Feature Specification: TwelveLabs SDK 规范化升级

**Feature Branch**: `001-twelvelabs-sdk-upgrade`
**Created**: 2025-12-30
**Status**: Draft
**Input**: User description: "根据官方文档https://docs.twelvelabs.io/sdk-reference/python规范项目"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 开发者使用标准化 SDK 调用方式 (Priority: P1)

作为开发者，我希望项目中的 TwelveLabs SDK 调用方式符合官方文档规范，以便获得更好的类型提示、错误处理和可维护性。

**Why this priority**: 这是本次规范化的核心目标，直接影响代码质量和后续维护成本。

**Independent Test**: 可以通过运行现有的视频搜索功能验证，确保搜索结果正常返回且类型正确。

**Acceptance Scenarios**:

1. **Given** 项目使用 TwelveLabs SDK，**When** 开发者查看客户端初始化代码，**Then** 应看到符合官方文档的标准初始化方式
2. **Given** 项目调用搜索 API，**When** 执行视频搜索，**Then** 应使用官方推荐的 `client.search.query()` 方法和参数格式
3. **Given** SDK 返回搜索结果，**When** 处理返回数据，**Then** 应正确使用官方定义的返回类型（video_id, score, start, end, confidence）

---

### User Story 2 - 系统正确处理 SDK 异常 (Priority: P1)

作为系统运维人员，我希望系统能正确捕获和处理 TwelveLabs SDK 的各类异常，以便快速定位问题并提供友好的错误信息。

**Why this priority**: 错误处理直接影响系统稳定性和问题排查效率，与核心功能同等重要。

**Independent Test**: 可以通过模拟网络错误、无效 API Key 等场景验证异常处理逻辑。

**Acceptance Scenarios**:

1. **Given** API Key 无效，**When** 初始化客户端或发起请求，**Then** 系统应捕获 AuthenticationError 并记录明确的错误日志
2. **Given** 请求频率超限，**When** 发起搜索请求，**Then** 系统应捕获 RateLimitError 并触发重试或降级策略
3. **Given** 服务端错误，**When** 发起请求，**Then** 系统应捕获 InternalServerError 并记录详细错误信息
4. **Given** 请求参数错误，**When** 发起搜索请求，**Then** 系统应捕获 BadRequestError 并提供有意义的错误提示

---

### User Story 3 - 开发者获得完整类型提示 (Priority: P2)

作为开发者，我希望在 IDE 中编写 TwelveLabs 相关代码时获得完整的类型提示，以便减少错误并提高开发效率。

**Why this priority**: 类型提示提升开发体验，但不影响运行时功能。

**Independent Test**: 可以通过 mypy 类型检查验证类型注解的完整性。

**Acceptance Scenarios**:

1. **Given** 开发者在 IDE 中编写代码，**When** 调用 TwelveLabs 客户端方法，**Then** 应显示完整的参数类型提示
2. **Given** 项目运行 mypy 类型检查，**When** 检查 TwelveLabs 相关代码，**Then** 不应出现类型错误（除已标注的 ignore）

---

### User Story 4 - 系统支持视频分析功能 (Priority: P3)

作为产品经理，我希望系统能利用 TwelveLabs 的视频分析功能（生成标题、摘要、高光），以便为用户提供更丰富的视频信息。

**Why this priority**: 这是增强功能，当前核心流程（搜索+渲染）不依赖此功能。

**Independent Test**: 可以通过调用视频分析 API 并验证返回结果格式来测试。

**Acceptance Scenarios**:

1. **Given** 系统已索引视频，**When** 请求生成视频高光，**Then** 应返回包含时间戳的高光片段列表
2. **Given** 系统已索引视频，**When** 请求生成视频摘要，**Then** 应返回结构化的摘要内容

---

### Edge Cases

- 当 TwelveLabs API 返回空结果时，系统应返回空列表并记录日志（当前已有 fallback 逻辑）
- 当搜索结果中的时间戳为 null 时，系统应跳过该结果并记录警告（当前已有过滤逻辑）
- 当视频时长获取失败时，片尾过滤应跳过该视频的片尾检查（当前已有缓存失败处理）
- 当多个 base_url 都失败时，系统应降级到 mock 模式（当前已有 mock 模式）
- 当 SDK 版本不支持某些高级参数时，系统应优雅降级到基础搜索

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 使用官方推荐的 `TwelveLabs` 类初始化客户端
- **FR-002**: 系统 MUST 使用 `client.search.query()` 方法执行视频搜索，参数包括 `index_id`、`query_text`、`search_options`、`group_by`、`page_limit`
- **FR-003**: 系统 MUST 正确处理搜索结果的分页（通过 pager 迭代）
- **FR-004**: 系统 MUST 捕获并处理官方定义的异常类型：`BadRequestError`、`AuthenticationError`、`NotFoundError`、`RateLimitError`、`InternalServerError`
- **FR-005**: 系统 MUST 在日志中记录 API 调用的关键信息（query、options、base_url、错误详情）
- **FR-006**: 系统 SHOULD 使用官方 SDK 的类型定义，避免使用 `Any` 类型
- **FR-007**: 系统 SHOULD 支持 Marengo 3.0 的高级搜索参数（transcription_options、operator、adjust_confidence_level）
- **FR-008**: 系统 SHOULD 使用 `client.index.video.retrieve()` 获取视频元数据（时长等）
- **FR-009**: 系统 MAY 使用 `client.gist()` 和 `client.summarize()` 进行视频分析

### Key Entities

- **TwelveLabsClient**: 封装 SDK 客户端的服务类，负责初始化、搜索、结果转换
- **TwelveLabsMatch**: 搜索结果的数据类，包含 video_id、start、end、score、rank 等字段
- **SearchOptions**: 搜索模态配置，支持 visual、audio、transcription

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 所有 TwelveLabs API 调用方式符合官方 SDK 文档规范
- **SC-002**: mypy 类型检查通过，TwelveLabs 相关代码无类型错误
- **SC-003**: 现有的视频搜索功能正常工作，搜索结果格式不变
- **SC-004**: 异常处理覆盖官方定义的 5 种异常类型（400/401/404/429/5xx）
- **SC-005**: 结构化日志包含 API 调用的关键追踪信息

## Assumptions

- 当前项目使用的 `twelvelabs>=0.1.7` 版本已支持本规范中提到的所有 API
- TwelveLabs SDK 的异步支持通过 `anyio.to_thread.run_sync` 实现（SDK 本身是同步的）
- 现有的 base_url failover 机制和 mock 模式需要保留
- 现有的片头/片尾过滤逻辑和视频去重逻辑需要保留

## Out of Scope

- 升级 TwelveLabs SDK 版本（如有需要，作为单独任务）
- 修改现有的业务逻辑（搜索策略、评分算法等）
- 添加新的 TwelveLabs 功能（如嵌入向量创建）

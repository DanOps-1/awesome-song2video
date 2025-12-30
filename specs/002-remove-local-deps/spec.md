# Feature Specification: 移除本地依赖，纯云端化

**Feature Branch**: `002-remove-local-deps`
**Created**: 2025-12-30
**Status**: Draft
**Input**: User description: "项目只用twelve labs api实现，其他的本地实现请删除，例如whisper（用在线搜索歌词替代，降低配置要求）、本地视频嵌入、本地视频向量数据库等"

## Overview

本项目当前混合使用云端服务（TwelveLabs API）和多个本地组件（Whisper ASR、本地视频嵌入、向量数据库等）。为降低部署配置要求、简化架构，需移除所有本地重型依赖，统一使用云端服务实现所有功能。

**核心变更**:
- 移除 Whisper ASR → 使用在线歌词搜索服务替代
- 移除本地视频嵌入 → 仅使用 TwelveLabs 云端视频索引
- 移除本地向量数据库 → 使用 TwelveLabs 云端搜索
- 移除相关本地依赖包（torch、transformers、openai-whisper 等重型 GPU 依赖）
- 保留 librosa（节拍检测，纯 CPU，约 50MB）和 FFmpeg（视频渲染）

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 在线歌词获取替代 Whisper (Priority: P1)

用户上传音频文件后，系统通过在线歌词服务（QQ音乐、网易云音乐、酷狗音乐、LRCLIB）自动搜索并获取歌词，无需本地 Whisper 语音识别。

**Why this priority**: 移除 Whisper 是最大的配置简化点。Whisper 需要 GPU 和大量内存，移除后可大幅降低服务器配置要求。同时，在线歌词质量通常优于语音识别。

**Independent Test**: 上传一首已知歌曲，系统能在 5 秒内从在线服务获取准确的时间轴歌词，无需本地 ASR。

**Acceptance Scenarios**:

1. **Given** 用户上传一首流行歌曲音频, **When** 系统处理该音频, **Then** 系统自动从在线歌词库搜索并获取 LRC 格式歌词
2. **Given** 用户提供歌曲名称和歌手信息, **When** 在线歌词搜索无结果, **Then** 系统提示用户手动输入歌词
3. **Given** 用户上传原创或冷门歌曲, **When** 所有在线歌词源均无结果, **Then** 系统允许用户手动输入或导入歌词文件

---

### User Story 2 - TwelveLabs 云端视频搜索 (Priority: P1)

所有视频片段搜索和匹配完全通过 TwelveLabs API 实现，移除任何本地视频嵌入或向量数据库组件。

**Why this priority**: 与 US1 同等重要。移除本地视频处理可消除对 GPU、大内存和本地存储的需求，显著简化部署。

**Independent Test**: 输入一句歌词描述，系统能在 3 秒内从 TwelveLabs 云端返回匹配的视频片段，无任何本地嵌入计算。

**Acceptance Scenarios**:

1. **Given** 系统已配置 TwelveLabs API, **When** 用户请求视频匹配, **Then** 系统仅通过 TwelveLabs Search API 获取匹配片段
2. **Given** TwelveLabs API 暂时不可用, **When** 用户请求视频匹配, **Then** 系统返回友好错误提示，建议稍后重试
3. **Given** 歌词描述较为抽象, **When** 系统搜索视频, **Then** 系统使用查询改写服务优化搜索词（已有功能）

---

### User Story 3 - 精简依赖配置 (Priority: P2)

移除不再需要的重型 Python 依赖包，降低安装和运行的硬件要求。

**Why this priority**: 这是 US1 和 US2 的自然结果。移除代码后需同步清理依赖，否则用户仍需安装不必要的包。

**Independent Test**: 在一台 2GB 内存、无 GPU 的服务器上，能成功安装并运行项目。

**Acceptance Scenarios**:

1. **Given** 项目 requirements 已更新, **When** 用户执行依赖安装, **Then** 不会安装 torch、transformers、whisper 等大型包
2. **Given** 新环境安装项目, **When** 用户执行依赖同步, **Then** 安装时间不超过 2 分钟（排除网络因素）
3. **Given** 清理后的代码库, **When** 运行 lint 和类型检查, **Then** 无未使用导入或类型错误

---

### User Story 4 - 代码清理和文档更新 (Priority: P3)

移除所有与本地依赖相关的代码、配置和文档，保持代码库整洁。

**Why this priority**: 确保长期可维护性。遗留的死代码会造成混淆。

**Independent Test**: 代码库中搜索 "whisper"、"embedding"、"vector" 等关键词，无相关功能代码残留。

**Acceptance Scenarios**:

1. **Given** 代码清理完成, **When** 搜索 Whisper 相关代码, **Then** 仅在历史记录和迁移说明中找到引用
2. **Given** README 已更新, **When** 新用户阅读文档, **Then** 无需配置 GPU 或安装 Whisper 即可运行项目
3. **Given** 配置文件已清理, **When** 查看环境变量说明, **Then** 无 Whisper 模型路径等已废弃配置

---

### Edge Cases

- 在线歌词服务全部不可用时，系统如何处理？→ 允许用户手动输入歌词
- TwelveLabs API 额度用尽时如何提示用户？→ 显示明确错误信息，引导用户检查 API 配额
- 迁移期间如何处理已有的本地数据？→ 本次不考虑数据迁移，假设全新部署
- 用户上传的音频如何识别歌曲信息？→ 依赖用户提供歌曲名和歌手名，或使用音频指纹服务（如 ACRCloud，可选）

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 通过在线歌词服务获取歌词，支持 QQ音乐、网易云音乐、酷狗音乐、LRCLIB
- **FR-002**: 系统 MUST 移除所有 Whisper ASR 相关代码和依赖
- **FR-003**: 系统 MUST 仅使用 TwelveLabs API 进行视频搜索和匹配
- **FR-004**: 系统 MUST 移除本地视频嵌入模块和向量数据库
- **FR-005**: 系统 MUST 移除 torch、transformers、openai-whisper 等 GPU 依赖包（保留 librosa 用于节拍检测）
- **FR-006**: 系统 MUST 在歌词搜索失败时允许用户手动输入
- **FR-007**: 系统 MUST 在 API 不可用时显示友好错误提示
- **FR-008**: 系统 MUST 更新文档反映新的最低配置要求

### Key Entities

- **歌词来源**: 在线歌词服务（已有 LyricsFetcher 支持 QQ/网易/酷狗/LRCLIB）
- **视频索引**: TwelveLabs 云端索引（已有 TwelveLabsClient）
- **用户输入**: 歌曲名、歌手名、音频文件

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 项目可在 2GB 内存、无 GPU 的服务器上正常运行
- **SC-002**: 依赖安装时间从当前的 10+ 分钟降低到 2 分钟以内
- **SC-003**: Docker 镜像大小从当前的 8GB+ 降低到 2GB 以内
- **SC-004**: 95% 的流行歌曲能在 5 秒内从在线服务获取歌词
- **SC-005**: 代码库中无 Whisper、本地嵌入相关的功能代码残留
- **SC-006**: 所有现有测试通过（移除已废弃功能的测试）
- **SC-007**: README 和部署文档更新，反映简化后的配置要求

## Assumptions

- 在线歌词服务（QQ音乐等）的可用性和覆盖率足以满足大多数用户需求
- TwelveLabs API 的稳定性和响应速度满足生产环境要求
- 用户愿意提供歌曲名和歌手名以辅助歌词搜索
- 不需要处理已有的本地数据迁移（假设全新部署）
- 保留 FFmpeg 用于视频渲染（轻量级依赖）
- 保留 librosa 用于节拍检测和卡点功能（纯 CPU，约 50MB，不需要 GPU）

## Out of Scope

- 音频指纹识别（ACRCloud 等）- 可作为后续增强
- 离线模式支持
- 本地数据迁移工具
- TwelveLabs 备选方案（其他视频搜索 API）

## Clarifications

### Session 2025-12-30

- Q: librosa 用于音乐节拍分析，是否也要移除？ → A: 保留 librosa，继续支持节拍卡点功能（不需要 GPU，约 50MB）

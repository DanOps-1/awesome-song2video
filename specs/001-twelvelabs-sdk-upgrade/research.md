# Research: TwelveLabs SDK 规范化

**Date**: 2025-12-30
**Feature**: 001-twelvelabs-sdk-upgrade

## 1. TwelveLabs Python SDK 异常类型

### 研究结果

根据官方 GitHub 仓库和文档，TwelveLabs Python SDK 定义了以下异常类型：

| 异常类型 | HTTP 状态码 | 触发场景 |
|----------|-------------|----------|
| `BadRequestError` | 400 | 请求参数错误（无效的 index_id、query 格式等） |
| `AuthenticationError` | 401 | API Key 无效或过期 |
| `NotFoundError` | 404 | 资源不存在（index、video 等） |
| `RateLimitError` | 429 | 请求频率超限 |
| `InternalServerError` | 5xx | 服务端错误 |

### 导入方式

```python
from twelvelabs.exceptions import (
    BadRequestError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    InternalServerError,
)
```

### 决策

- **Decision**: 使用官方异常类型进行精细化捕获
- **Rationale**: 官方异常类型已足够细粒度，无需自定义包装
- **Alternatives considered**:
  - 继续使用通用 Exception → 拒绝：无法区分错误类型
  - 自定义异常层 → 拒绝：增加不必要复杂度

## 2. SDK 客户端初始化

### 研究结果

官方推荐的初始化方式：

```python
from twelvelabs import TwelveLabs

client = TwelveLabs(api_key="<YOUR_API_KEY>")
# 或使用自定义 base_url
client = TwelveLabs(api_key="<YOUR_API_KEY>", base_url="https://api.twelvelabs.io/v1.3")
```

### 当前项目实现

项目已符合官方规范：
- 使用 `TwelveLabs` 类初始化
- 支持自定义 `base_url`
- 支持 failover 机制（多个 base_url 备选）

### 决策

- **Decision**: 保持现有初始化方式，无需修改
- **Rationale**: 已符合官方规范，且有额外的 failover 能力

## 3. 搜索 API 调用

### 研究结果

官方搜索 API 调用方式：

```python
search_results = client.search.query(
    index_id="<INDEX_ID>",
    query_text="<QUERY>",
    search_options=["visual", "audio"],  # 可选模态
    group_by="clip",  # 按片段分组
    page_limit=10,  # 每页结果数
)
```

返回字段：
- `video_id`: 视频 ID
- `score`: 匹配分数
- `start`: 开始时间（秒）
- `end`: 结束时间（秒）
- `confidence`: 置信度（可选）

### 当前项目实现

项目已符合官方规范：
- 使用 `client.search.query()` 方法
- 参数格式正确
- 支持 Marengo 3.0 高级参数

### 决策

- **Decision**: 保持现有搜索调用方式，无需修改
- **Rationale**: 已符合官方规范

## 4. 类型提示改进

### 研究结果

当前代码中的 `Any` 类型使用：

1. `self._client: Any | None` - SDK 客户端实例
2. `cast(Any, self._client)` - 调用 SDK 方法时的类型转换
3. `Iterable[Any]` - 搜索结果迭代器

### 改进方案

```python
from twelvelabs import TwelveLabs

class TwelveLabsClient:
    def __init__(self) -> None:
        self._client: TwelveLabs | None = None
```

对于搜索结果，SDK 返回的是 `SearchData` 类型，但由于 SDK 类型导出不完整，建议：
- 保持 `Iterable[Any]` 但添加注释说明
- 或使用 `TYPE_CHECKING` 条件导入

### 决策

- **Decision**: 将 `_client` 类型从 `Any` 改为 `TwelveLabs | None`，其他保持现状并添加注释
- **Rationale**: 在 SDK 类型支持范围内改进，避免过度工程
- **Alternatives considered**:
  - 完全移除所有 Any → 拒绝：SDK 类型导出不完整
  - 自定义 TypedDict → 拒绝：增加维护负担

## 5. 视频分析 API（可选）

### 研究结果

TwelveLabs 提供的视频分析 API：

```python
# 生成标题/话题/标签
gist = client.gist(video_id, types=["title", "topic", "hashtag"])

# 生成摘要/章节/高光
res = client.summarize(video_id, type="summary", prompt="<PROMPT>")

# 开放式分析
res = client.analyze(video_id, prompt="<PROMPT>")
```

### 当前项目使用

项目在 `action_detector.py` 中已使用 `client.generate.summarize()` 获取视频高光。

### 决策

- **Decision**: 保持现有实现，仅改进异常处理
- **Rationale**: 功能已实现，本次重构聚焦于代码质量

## 总结

| 领域 | 当前状态 | 需要修改 |
|------|----------|----------|
| 客户端初始化 | ✅ 符合规范 | 否 |
| 搜索 API 调用 | ✅ 符合规范 | 否 |
| 异常处理 | ⚠️ 使用通用 Exception | **是** |
| 类型提示 | ⚠️ 过多 Any 类型 | **是** |
| 视频分析 API | ✅ 已实现 | 仅改进异常处理 |

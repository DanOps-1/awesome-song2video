# Data Model: TwelveLabs SDK 异常与类型

**Date**: 2025-12-30
**Feature**: 001-twelvelabs-sdk-upgrade

## 1. SDK 异常类型层次

```
BaseException
└── Exception
    └── TwelveLabsError (SDK 基类)
        ├── BadRequestError (400)
        ├── AuthenticationError (401)
        ├── NotFoundError (404)
        ├── RateLimitError (429)
        └── InternalServerError (5xx)
```

## 2. 异常处理映射

| 异常类型 | 处理策略 | 日志级别 | 用户提示 |
|----------|----------|----------|----------|
| `BadRequestError` | 记录并返回空结果 | WARNING | 搜索参数无效 |
| `AuthenticationError` | 记录并抛出 | ERROR | API 配置错误 |
| `NotFoundError` | 记录并返回空结果 | WARNING | 资源不存在 |
| `RateLimitError` | 重试或降级 | WARNING | 请求过于频繁 |
| `InternalServerError` | failover 或降级 | ERROR | 服务暂时不可用 |

## 3. 现有数据类型

### TwelveLabsMatch

```python
@dataclass
class TwelveLabsMatch:
    """搜索结果数据类"""
    id: str              # 唯一标识（UUID）
    video_id: str        # TwelveLabs 视频 ID
    start: int           # 开始时间（毫秒）
    end: int             # 结束时间（毫秒）
    score: float         # 匹配分数（0.0-1.0）
    rank: int | None     # 排名（可选）
    preview: str | None  # 预览 URL（可选）
```

### 搜索结果字典

```python
# 返回给调用方的字典格式（保持不变）
{
    "id": str,           # UUID
    "video_id": str,     # 视频 ID
    "start": int,        # 毫秒
    "end": int,          # 毫秒
    "score": float,      # 0.0-1.0
    "rank": int | None,  # 排名
}
```

## 4. 类型改进计划

### 改进前

```python
class TwelveLabsClient:
    def __init__(self) -> None:
        self._client: Any | None = None  # ❌ Any 类型
```

### 改进后

```python
from twelvelabs import TwelveLabs

class TwelveLabsClient:
    def __init__(self) -> None:
        self._client: TwelveLabs | None = None  # ✅ 具体类型
```

## 5. 日志事件定义

| 事件名 | 触发场景 | 包含字段 |
|--------|----------|----------|
| `twelvelabs.search_query` | 发起搜索 | query, base_url, options |
| `twelvelabs.search_success` | 搜索成功 | query, result_count |
| `twelvelabs.search_empty` | 搜索无结果 | query, options |
| `twelvelabs.search_failed` | 搜索失败 | error, error_type, base_url |
| `twelvelabs.auth_error` | 认证失败 | error |
| `twelvelabs.rate_limit` | 频率限制 | retry_after |
| `twelvelabs.client_failover` | 客户端切换 | old_url, new_url |

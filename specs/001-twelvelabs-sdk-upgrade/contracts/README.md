# API Contracts: TwelveLabs SDK 规范化

**Date**: 2025-12-30
**Feature**: 001-twelvelabs-sdk-upgrade

## 说明

本次重构是内部代码质量改进，**不涉及外部 API 变更**。

现有 API 端点保持不变：
- `POST /api/v1/mixes` - 创建混剪请求
- `POST /api/v1/mixes/{id}/transcribe` - 转录歌词
- `GET /api/v1/mixes/{id}/preview` - 获取预览

## 内部接口变更

### TwelveLabsClient.search_segments()

**签名不变**：
```python
async def search_segments(self, query: str, limit: int = 5) -> list[dict[str, Any]]
```

**返回格式不变**：
```json
[
  {
    "id": "uuid",
    "video_id": "tl_video_id",
    "start": 1000,
    "end": 2500,
    "score": 0.85,
    "rank": 1
  }
]
```

**行为变更**：
- 异常处理更精细（区分 400/401/404/429/5xx）
- 日志包含更多上下文信息

## 无破坏性变更

本次重构保证：
1. 返回数据格式完全兼容
2. 现有调用方无需修改
3. 错误处理行为向后兼容（仍返回空列表或抛出异常）

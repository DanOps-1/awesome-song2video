# API Contracts: 移除本地依赖

**Date**: 2025-12-30
**Feature**: 002-remove-local-deps

## 概述

本次重构对 API 的影响极小。主要变更是 `/transcribe` 端点的行为变化。

## 变更的端点

### POST /api/v1/mixes/{id}/transcribe

**原行为**: 触发 Whisper ASR 转录音频，返回任务状态

**新行为**: 返回 410 Gone 或 400 Bad Request，提示功能已移除

```yaml
paths:
  /api/v1/mixes/{id}/transcribe:
    post:
      summary: "[已弃用] 触发音频转录"
      deprecated: true
      responses:
        "410":
          description: 功能已移除
          content:
            application/json:
              schema:
                type: object
                properties:
                  detail:
                    type: string
                    example: "Whisper 转录功能已移除。请使用 /fetch-lyrics 获取在线歌词，或 /import-lyrics 手动导入。"
```

### 替代方案

用户应使用以下端点获取歌词：

| 端点 | 用途 | 状态 |
|------|------|------|
| `POST /api/v1/mixes/{id}/fetch-lyrics` | 从在线服务搜索歌词 | ✅ 无变更 |
| `POST /api/v1/mixes/{id}/import-lyrics` | 手动导入歌词 | ✅ 无变更 |

## 保持不变的端点

以下端点无任何变更：

- `POST /api/v1/mixes` - 创建请求
- `GET /api/v1/mixes/{id}` - 获取状态
- `GET /api/v1/mixes/{id}/lines` - 获取歌词行
- `PATCH /api/v1/mixes/{id}/lines/{line_id}` - 编辑歌词行
- `POST /api/v1/mixes/{id}/preview` - 获取预览
- `POST /api/v1/mixes/{id}/render` - 触发渲染
- `POST /api/v1/mixes/{id}/analyze-beats` - 节拍分析
- `GET /api/v1/mixes/{id}/beats` - 获取节拍数据

## 向后兼容性

| 场景 | 兼容性 | 说明 |
|------|--------|------|
| 调用 `/transcribe` | ⚠️ Breaking | 返回错误，需改用其他端点 |
| 检查 `transcribing` 状态 | ✅ 兼容 | 状态枚举保留，但不再使用 |
| 其他 API 调用 | ✅ 兼容 | 无变更 |

## 客户端迁移指南

### 旧流程
```
1. POST /mixes - 创建请求
2. POST /mixes/{id}/transcribe - 等待转录完成
3. GET /mixes/{id}/lines - 获取歌词
4. POST /mixes/{id}/render - 渲染
```

### 新流程
```
1. POST /mixes - 创建请求
2. POST /mixes/{id}/fetch-lyrics - 获取在线歌词
   或 POST /mixes/{id}/import-lyrics - 手动导入
3. GET /mixes/{id}/lines - 获取歌词
4. POST /mixes/{id}/render - 渲染
```

**主要变化**: 第 2 步从 `transcribe` 改为 `fetch-lyrics` 或 `import-lyrics`。

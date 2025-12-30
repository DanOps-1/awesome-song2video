# Data Model: 移除本地依赖

**Date**: 2025-12-30
**Feature**: 002-remove-local-deps

## 概述

本次重构**不涉及数据模型变更**。现有数据库表结构保持不变，仅移除不再使用的代码路径。

## 现有模型（保持不变）

### SongMixRequest

主请求实体，状态枚举保持不变：

```python
class MixStatus(str, Enum):
    pending = "pending"           # 待处理
    transcribing = "transcribing" # 转录中（不再使用，保留兼容）
    transcribed = "transcribed"   # 歌词已确认
    matching = "matching"         # 视频匹配中
    generated = "generated"       # 时间线已生成
    rendering = "rendering"       # 渲染中
    completed = "completed"       # 完成
    failed = "failed"             # 失败
```

**注意**: `transcribing` 状态保留以兼容历史数据，但新流程不再使用。

### LyricLine

歌词行实体，无变更：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| mix_id | int | 关联请求 |
| line_index | int | 行号 |
| text | str | 歌词文本 |
| start_ms | int | 开始时间 |
| end_ms | int | 结束时间 |

### VideoSegmentMatch

视频匹配结果，无变更。

### RenderJob

渲染任务，无变更。

### BeatAnalysisData

节拍分析数据，无变更（librosa 保留）。

## 状态流变更

### 原流程（包含 Whisper）

```
pending
   ↓
transcribing  ← Whisper ASR
   ↓
transcribed
   ↓
matching
   ↓
generated
   ↓
rendering
   ↓
completed
```

### 新流程（纯在线歌词）

```
pending
   ↓
   ├── fetch-lyrics (在线搜索)
   │   └── transcribed
   │
   └── import-lyrics (手动导入)
       └── transcribed
   ↓
matching
   ↓
generated
   ↓
rendering
   ↓
completed
```

**关键变化**: 跳过 `transcribing` 状态，直接从 `pending` 到 `transcribed`。

## 迁移策略

**无需数据迁移**。

- 现有处于 `transcribing` 状态的请求可手动重置为 `pending`
- 已有的 `transcribed` 数据保持不变
- 数据库 schema 无变更

## 配置变更

### 移除的配置项

| 配置项 | 原用途 |
|--------|--------|
| `WHISPER_MODEL_NAME` | Whisper 模型名称 |
| `WHISPER_DEVICE` | 运行设备 (cuda/cpu) |
| `WHISPER_LANGUAGE` | 默认语言 |

### 保留的配置项

| 配置项 | 用途 |
|--------|------|
| `TL_API_KEY` | TwelveLabs API |
| `DEEPSEEK_API_KEY` | 查询改写 |
| `BEAT_SYNC_*` | 节拍对齐配置 |

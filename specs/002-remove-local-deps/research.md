# Research: 移除本地依赖

**Date**: 2025-12-30
**Feature**: 002-remove-local-deps

## 1. Whisper 代码分布

### 需要删除的文件

| 文件 | 说明 | 操作 |
|------|------|------|
| `src/audio/transcriber.py` | Whisper 转录器主类 | 🗑️ 删除 |
| `src/pipelines/lyrics_ingest/transcriber.py` | 歌词转录管道 | 🗑️ 删除 |

### 需要修改的文件

| 文件 | 说明 | 修改内容 |
|------|------|----------|
| `src/audio/__init__.py` | 模块导出 | 移除 transcriber 导入 |
| `src/infra/config/settings.py` | 配置类 | 移除 whisper_model_name 等配置 |
| `src/workers/timeline_worker.py` | 时间线 Worker | 移除 transcribe_lyrics 任务 |
| `src/pipelines/matching/timeline_builder.py` | 时间线构建器 | 移除 Whisper 相关逻辑 |
| `src/domain/models/song_mix.py` | 领域模型 | 检查状态枚举 |
| `src/api/v1/routes/mixes.py` | API 路由 | 移除/修改 transcribe 端点 |
| `src/api/v1/routes/admin/config.py` | 管理配置 | 移除 Whisper 配置项 |
| `src/timeline/builder.py` | 旧时间线构建器 | 检查是否仍在使用 |
| `src/lyrics/fetcher.py` | 歌词获取器 | 检查 Whisper 引用（可能仅注释） |

### 需要检查的测试文件

| 文件 | 说明 |
|------|------|
| `tests/integration/test_timeline_gaps.py` | 可能引用 transcribe |
| `tests/integration/test_timeline_generation.py` | 可能引用 transcribe |
| `tests/contract/test_mix_lines_edit.py` | 可能引用 transcribe 状态 |

## 2. 依赖关系分析

### 需要移除的依赖

| 包名 | 大小 | 说明 | 决策 |
|------|------|------|------|
| `openai-whisper` | ~1.5GB（含模型） | Whisper ASR | 🗑️ 移除 |

### 间接依赖（Whisper 引入）

openai-whisper 依赖以下包，移除后可能被自动清理：
- `torch` - 深度学习框架（~2GB）
- `transformers` - Hugging Face（可选，取决于版本）
- `tiktoken` - 分词器
- `numba` - JIT 编译器
- `llvmlite` - LLVM 绑定

**注意**: librosa 也依赖 numba，但 librosa 被保留。需验证 librosa 是否可独立安装。

### 保留的依赖

| 包名 | 说明 | 决策 |
|------|------|------|
| `librosa` | 节拍检测 | ✅ 保留 |
| `pydub` | 音频处理 | ✅ 保留 |
| `python-ffmpeg` | FFmpeg 绑定 | ✅ 保留 |

## 3. API 影响分析

### 受影响的端点

| 端点 | 当前行为 | 变更后行为 |
|------|----------|------------|
| `POST /api/v1/mixes/{id}/transcribe` | 触发 Whisper 转录 | 返回错误提示，引导用户使用在线歌词 |
| `POST /api/v1/mixes/{id}/fetch-lyrics` | 在线歌词搜索 | 无变更，成为主要方式 |
| `POST /api/v1/mixes/{id}/import-lyrics` | 手动导入歌词 | 无变更 |

### 状态流变更

**当前流程**:
```
pending → transcribing → transcribed → matching → generated
```

**变更后流程**:
```
pending → (fetch-lyrics 或 import) → transcribed → matching → generated
```

`transcribing` 状态不再使用，但可保留以兼容旧数据。

## 4. 决策记录

### D1: 移除 openai-whisper

**Decision**: 移除 openai-whisper 及其全部依赖
**Rationale**:
- Whisper 是最大的配置要求来源（GPU、大内存）
- 在线歌词服务（QQ/网易/酷狗/LRCLIB）覆盖率高
- 用户可手动导入歌词作为兜底
**Alternatives Rejected**:
- 保留 Whisper 作为可选功能 → 增加维护复杂度，不符合简洁性原则

### D2: 保留 librosa

**Decision**: 保留 librosa 用于节拍检测
**Rationale**:
- librosa 是纯 CPU 库，不需要 GPU
- 安装大小约 50MB，对配置要求影响极小
- 节拍卡点是产品差异化功能
**Alternatives Rejected**:
- 移除节拍功能 → 降低产品价值
- 使用云端节拍检测 → 增加外部依赖和成本

### D3: transcribe API 处理

**Decision**: 保留 `/transcribe` 端点但返回错误提示
**Rationale**:
- 保持 API 向后兼容性
- 明确引导用户使用替代方案
**Alternatives Rejected**:
- 直接删除端点 → 可能破坏现有客户端
- 静默失败 → 用户体验差

## 5. 验证方案

### 依赖验证

```bash
# 移除 whisper 后验证 librosa 可独立安装
uv pip install librosa --no-deps
uv run python -c "import librosa; print(librosa.__version__)"
```

### 功能验证

1. 在线歌词搜索正常工作
2. 节拍检测正常工作（librosa）
3. 视频渲染正常工作（FFmpeg）
4. API 端点返回正确状态码

### 镜像大小验证

```bash
# 构建 Docker 镜像并检查大小
docker build -t song2video:test .
docker images song2video:test --format "{{.Size}}"
# 目标: < 2GB
```

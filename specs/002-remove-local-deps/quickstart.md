# Quickstart: 移除本地依赖验证

**Date**: 2025-12-30
**Feature**: 002-remove-local-deps

## 验证清单

完成实现后，执行以下验证步骤：

### 1. 依赖验证

```bash
# 确认 whisper 已移除
uv run python -c "import whisper" 2>&1 | grep -q "No module" && echo "✅ Whisper 已移除" || echo "❌ Whisper 仍存在"

# 确认 librosa 仍可用
uv run python -c "import librosa; print(f'✅ librosa {librosa.__version__}')"

# 确认依赖大小
uv pip list | wc -l
```

### 2. 代码检查

```bash
# Ruff lint
uv run ruff check src tests

# Ruff format
uv run ruff format --check src tests

# mypy 类型检查
uv run mypy src
```

### 3. 功能验证

```bash
# 运行测试
uv run pytest tests/ -v

# 验证在线歌词搜索
uv run python -m src.lyrics.fetcher "稻香" "周杰伦"

# 验证节拍检测（需要音频文件）
# uv run python -c "from src.audio.beat_detector import BeatDetector; print('✅ BeatDetector 可用')"
```

### 4. API 验证

```bash
# 启动服务
uv run python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
sleep 3

# 健康检查
curl -s http://localhost:8000/health | jq .

# 验证 /transcribe 返回错误
curl -s -X POST http://localhost:8000/api/v1/mixes/1/transcribe | jq .

# 停止服务
pkill -f "uvicorn src.api.main:app"
```

### 5. Docker 镜像验证（可选）

```bash
# 构建镜像
docker build -t song2video:test .

# 检查大小
docker images song2video:test --format "大小: {{.Size}}"
# 期望: < 2GB

# 运行容器验证
docker run --rm song2video:test python -c "import librosa; print('✅ 容器内 librosa 可用')"
```

## 预期结果

| 检查项 | 预期 |
|--------|------|
| Whisper 导入 | ❌ 失败（ModuleNotFoundError） |
| librosa 导入 | ✅ 成功 |
| Ruff 检查 | ✅ 无错误 |
| mypy 检查 | ✅ 无错误 |
| pytest | ✅ 全部通过 |
| Docker 镜像大小 | < 2GB |
| 内存占用 | < 2GB（无 GPU） |

## 回滚方案

如果验证失败，可通过以下方式回滚：

```bash
# 恢复 pyproject.toml
git checkout HEAD -- pyproject.toml

# 重新安装依赖
uv sync

# 恢复删除的文件
git checkout HEAD -- src/audio/transcriber.py
git checkout HEAD -- src/pipelines/lyrics_ingest/transcriber.py
```

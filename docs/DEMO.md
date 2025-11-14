# 功能演示：需求与实现对齐更新

## 演示概览

本演示展示了歌词混剪系统的三个核心功能：
1. **Preview Manifest API** - 查看完整时间线清单
2. **Render Metrics** - 量化渲染质量
3. **Fallback 追踪** - 追踪缺失媒资

## 快速开始

### 1. 运行端到端测试

```bash
# Preview API 测试
python scripts/dev/e2e_test.py

# Render Metrics 测试
python scripts/dev/e2e_render_test.py
```

**预期输出**: 所有测试通过，显示完整的 manifest 和 metrics

### 2. 查看测试结果

```bash
# 查看 Preview Metrics
sqlite3 dev.db "SELECT
  id,
  song_title,
  json_extract(metrics, '$.preview.fallback_count') as fallback_count,
  json_extract(metrics, '$.preview.avg_delta_ms') as avg_delta_ms
FROM song_mix_requests
WHERE song_title LIKE '%测试%';"

# 查看 Render Metrics
sqlite3 dev.db "SELECT
  id,
  job_status,
  json_extract(metrics, '$.render.avg_delta_ms') as avg_delta_ms,
  json_extract(metrics, '$.render.queued_at') as queued_at
FROM render_jobs
ORDER BY submitted_at DESC
LIMIT 5;"
```

## 功能演示

### Demo 1: Preview Manifest API

#### 场景说明
- 创建包含 3 行歌词的 mix
- 前 2 行有 TwelveLabs 候选片段
- 第 3 行无候选，触发 fallback

#### 执行步骤

```bash
# 1. 运行测试脚本
python scripts/dev/e2e_test.py
```

#### 输出示例

```json
{
  "manifest": [
    {
      "line_id": "...-line-1",
      "line_no": 1,
      "lyrics": "东临碣石，以观沧海",
      "source_video_id": "6911acda8bf751b791733149",
      "clip_start_ms": 1000,
      "clip_end_ms": 3500,
      "confidence": 0.92,
      "fallback": false,
      "fallback_reason": null
    },
    {
      "line_id": "...-line-3",
      "line_no": 3,
      "lyrics": "树木丛生，百草丰茂",
      "source_video_id": "6911acda8bf751b791733149",
      "clip_start_ms": 7500,
      "clip_end_ms": 11000,
      "confidence": 0.0,
      "fallback": true,
      "fallback_reason": "no_candidates_from_twelvelabs"
    }
  ],
  "metrics": {
    "line_count": 3,
    "total_duration_ms": 10000,
    "avg_delta_ms": 333.33,
    "max_delta_ms": 500.0,
    "fallback_count": 1,
    "generated_at": "2025-11-13T09:04:00.014015Z"
  }
}
```

#### 关键验证点

✅ **Manifest 完整性**
- 每行歌词都有对应的视频片段
- `fallback` 标志正确标识无候选的行
- `fallback_reason` 解释原因

✅ **Metrics 准确性**
- `line_count`: 3
- `fallback_count`: 1
- `avg_delta_ms`: 歌词与视频片段的平均对齐偏差
- `max_delta_ms`: 最大对齐偏差
- `generated_at`: ISO 8601 格式时间戳

✅ **日志追踪**
```
2025-11-13 17:04:00 [warning] preview.fallback_used
  fallback_reason=no_candidates_from_twelvelabs
  line_id=...-line-3
  line_no=3
  mix_id=...

2025-11-13 17:04:00 [info] preview.manifest_built
  avg_delta_ms=333.33
  fallback_count=1
  line_count=3
  max_delta_ms=500.0
  mix_id=...
```

### Demo 2: Render Metrics

#### 场景说明
- 创建 RenderJob
- 模拟渲染过程并计算对齐指标
- 保存完整的 RenderMetrics

#### 执行步骤

```bash
# 1. 运行测试脚本
python scripts/dev/e2e_render_test.py
```

#### 输出示例

```json
{
  "line_count": 3,
  "avg_delta_ms": 500.0,
  "max_delta_ms": 500,
  "total_duration_ms": 9000,
  "queued_at": "2025-11-13T09:05:20.302639Z",
  "finished_at": "2025-11-13T09:05:20.321372Z"
}
```

#### 关键验证点

✅ **Metrics 完整性**
- `line_count`: 渲染的歌词行数
- `avg_delta_ms`: 平均对齐偏差
- `max_delta_ms`: 最大对齐偏差
- `total_duration_ms`: 输出视频总时长

✅ **时间追踪**
- `queued_at`: 任务进入队列时间
- `finished_at`: 任务完成时间
- 时间戳格式: ISO 8601 (带 Z 后缀)

✅ **数据库持久化**
```sql
SELECT * FROM render_jobs WHERE id='...';
-- metrics 字段包含完整的 render 子键
```

### Demo 3: Fallback 追踪

#### 场景 3.1: TwelveLabs 无命中

**问题**: 某行歌词在 TwelveLabs 中找不到匹配的视频片段

**系统行为**:
1. 使用配置的 `FALLBACK_VIDEO_ID`
2. Manifest 标记 `fallback: true`
3. 记录 `fallback_reason: "no_candidates_from_twelvelabs"`
4. 输出警告日志

**验证方式**:
```bash
# 查看 manifest
python scripts/dev/e2e_test.py | grep -A 10 "fallback.*true"

# 查看日志（需要启动 API 服务）
# 日志包含: preview.fallback_used
```

#### 场景 3.2: MinIO 未启用

**问题**: 对象存储未配置，渲染产物无法上传

**系统行为**:
1. 渲染继续进行
2. 产物保存到本地临时目录
3. 输出 `render_worker.storage_todo` 警告
4. 记录本地文件路径

**验证方式**:
```python
# 在 render_worker.py 中查看日志
logger.warning(
    "render_worker.storage_todo",
    message="MinIO 未启用，产物仅存本地",
    local_path=output_object,
    subtitle_path=subtitle_file.as_posix(),
    job_id=job_id,
)
```

**排查步骤** (参见 `docs/lyrics_mix_runbook.md`):
1. 查看 Loki 日志: `{job="lyrics-mix-worker"} |= "storage_todo"`
2. 获取本地文件路径
3. 手动上传到对象存储
4. 或配置 MinIO 后重新渲染

## 技术亮点

### 1. 类型安全的 Metrics

```python
from src.domain.models.metrics import PreviewMetrics, RenderMetrics

# TypedDict 确保字段完整性
preview_metrics: PreviewMetrics = {
    "line_count": 3,
    "total_duration_ms": 10000,
    "avg_delta_ms": 333.33,
    "max_delta_ms": 500.0,
    "fallback_count": 1,
    "generated_at": "2025-11-13T09:04:00Z",
}
```

### 2. OTEL 指标推送

```python
from src.infra.observability.preview_render_metrics import (
    push_preview_metrics,
    push_render_metrics,
)

# 自动推送到 Prometheus
push_preview_metrics(
    mix_id=mix_id,
    line_count=3,
    avg_delta_ms=333.33,
    max_delta_ms=500.0,
    fallback_count=1,
    owner_id=owner_id,
)
```

### 3. 结构化日志

```python
import structlog

logger = structlog.get_logger(__name__)

# 所有关键事件都有结构化日志
logger.info(
    "preview.manifest_built",
    mix_id=mix_id,
    line_count=3,
    avg_delta_ms=333.33,
    fallback_count=1,
    generated_at=timestamp,
)
```

### 4. Fallback 优雅降级

```python
# 优先级：用户选中 > 第一个候选 > Fallback
def _select_segment(self, line: LyricLine) -> tuple[VideoSegmentMatch, bool, str | None]:
    candidates = getattr(line, "candidates", []) or []

    if line.selected_segment_id:
        # 用户选中的候选
        ...

    if candidates:
        # 第一个候选
        return (candidates[0], False, None)

    # Fallback
    return (fallback_segment, True, "no_candidates_from_twelvelabs")
```

## 监控与可观测性

### Prometheus 查询示例

```promql
# Preview 平均对齐偏差
avg(lyrics_preview_avg_delta_ms)

# Fallback 比例
sum(rate(lyrics_preview_fallback_count[5m])) /
sum(rate(lyrics_preview_line_count[5m]))

# Render 队列深度
render_queue_depth
```

### Loki 日志查询示例

```logql
# Preview 生成事件
{job="lyrics-mix-api"} |= "preview.manifest_built" | json

# Fallback 使用
{job="lyrics-mix-api"} |= "preview.fallback_used" | json

# 存储 TODO
{job="lyrics-mix-worker"} |= "render_worker.storage_todo" | json
```

### Grafana 仪表盘

配置文件: `observability/dashboards/lyrics_mix.json`

**包含面板**:
- Preview: 平均对齐偏差、最大对齐偏差、Fallback 行数
- Render: 对齐质量分布、渲染时长、队列深度
- Annotations: Preview 生成事件、Render 存储 TODO、Fallback 使用

## 故障排查示例

### 问题 1: Preview API 返回 404

**症状**: `GET /api/v1/mixes/{mix_id}/preview` 返回 404

**可能原因**:
1. Mix 不存在
2. Timeline 未生成 (`timeline_status != "generated"`)

**排查步骤**:
```bash
# 检查 mix 状态
sqlite3 dev.db "SELECT id, timeline_status FROM song_mix_requests WHERE id='...';"

# 查看 API 日志
# 应该包含: preview.api.mix_not_found 或 preview.api.timeline_not_ready
```

### 问题 2: Fallback 比例过高 (>30%)

**症状**: 大量歌词行使用 fallback 视频

**可能原因**:
1. TwelveLabs Index 质量问题
2. 检索参数不合适
3. 视频素材库不足

**排查步骤**:
```bash
# 查看 fallback 原因分布
# Loki 查询: {job="lyrics-mix-api"} |= "fallback_reason" | json

# 检查 TwelveLabs 配置
echo $TL_INDEX_ID

# 查看 Prometheus 指标
# sum(rate(lyrics_preview_fallback_count[5m])) / sum(rate(lyrics_preview_line_count[5m]))
```

## 总结

✅ **功能完整性**: 所有用户故事已实现
✅ **代码质量**: Ruff + Mypy 检查通过
✅ **可观测性**: 结构化日志 + OTEL 指标完整
✅ **数据持久化**: Metrics 正确保存到数据库
✅ **错误处理**: Fallback 优雅降级

**后续工作**:
1. 补充完整的单元测试和契约测试
2. 部署到测试环境
3. 配置 Prometheus 报警
4. 优化对齐质量达到 SC-001/SC-002 目标

---

**演示准备人**: Claude Code (Sonnet 4.5)
**文档日期**: 2025-11-13

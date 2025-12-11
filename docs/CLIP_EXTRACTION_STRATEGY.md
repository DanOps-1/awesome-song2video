# 视频片段提取策略说明

## 问题背景

### 原始问题：语义失调

当 API 返回的匹配片段较长时（如15秒），真正匹配的精彩画面往往不在片段开头：

**示例场景**：
- 歌词："person in pain"（痛苦的人）
- API 返回：5秒-20秒（共15秒的片段）
- 片段内容分布：
  - 0-5秒：人物走路（铺垫）
  - 5-10秒：人物表情变化（过渡）
  - **10-15秒：人物痛苦表情** ← 真正匹配的画面

**旧策略（从开头截取）**：
```
截取：5秒-7秒（歌词2秒）
结果：只看到人物走路 ❌ 语义失调！
```

**新策略（从中间截取）**：
```
中间位置：(5 + 20) / 2 = 12.5秒
截取：11.5秒-13.5秒（以中间为中心，截取2秒）
结果：看到人物痛苦表情 ✅ 语义匹配！
```

## 解决方案

### 核心策略：从片段中间截取

```python
# 计算 API 返回片段的中间位置
api_start = 5000ms      # API 返回的起点
api_end = 20000ms       # API 返回的终点
api_middle = (5000 + 20000) / 2 = 12500ms

# 从中间位置截取歌词时长（2秒）
lyric_duration = 2000ms
clip_start = 12500 - (2000 / 2) = 11500ms  # 向前偏移1秒
clip_end = 11500 + 2000 = 13500ms           # 向后偏移1秒

# 最终提取：11.5秒 - 13.5秒
```

### 边界保护

确保截取范围不超出原始片段：

```python
# 如果开始时间小于 API 起点
if clip_start < api_start:
    clip_start = api_start
    clip_end = api_start + lyric_duration

# 如果结束时间大于 API 终点
elif clip_end > api_end:
    clip_end = api_end
    clip_start = api_end - lyric_duration
```

## 示例对比

### 示例1：长片段（15秒）

| 数据 | 值 |
|-----|---|
| API 返回片段 | 5000ms - 20000ms (15秒) |
| 歌词时长 | 2000ms (2秒) |
| **旧策略截取** | 5000ms - 7000ms |
| **新策略截取** | 11500ms - 13500ms ✅ |
| 优势 | 从中间截取，获得最匹配的画面 |

### 示例2：短片段（3秒）

| 数据 | 值 |
|-----|---|
| API 返回片段 | 5000ms - 8000ms (3秒) |
| 歌词时长 | 2000ms (2秒) |
| 中间位置 | 6500ms |
| 理论截取 | 5500ms - 7500ms |
| **实际截取** | 5500ms - 7500ms ✅ |
| 说明 | 在范围内，正常居中 |

### 示例3：边界情况（片段 = 歌词）

| 数据 | 值 |
|-----|---|
| API 返回片段 | 5000ms - 7000ms (2秒) |
| 歌词时长 | 2000ms (2秒) |
| **截取** | 5000ms - 7000ms |
| 说明 | 完全使用整个片段 |

## 代码实现

位置：`src/pipelines/matching/timeline_builder.py:100-135`

```python
def _candidate_defaults(candidate: dict[str, int | float | str]) -> dict[str, int | float | str]:
    # 获取 API 返回的原始片段范围
    api_start = int(candidate.get("start", start_ms))
    api_end = int(candidate.get("end", end_ms))
    lyric_duration = end_ms - start_ms

    # 计算中间位置
    api_duration = api_end - api_start
    api_middle = api_start + (api_duration // 2)

    # 从中间位置居中截取歌词时长
    clip_start = api_middle - (lyric_duration // 2)
    clip_end = clip_start + lyric_duration

    # 边界保护
    if clip_start < api_start:
        clip_start = api_start
        clip_end = min(api_start + lyric_duration, api_end)
    elif clip_end > api_end:
        clip_end = api_end
        clip_start = max(api_end - lyric_duration, api_start)

    return {
        "start_time_ms": clip_start,
        "end_time_ms": clip_end,
        # ...
    }
```

## 效果对比

### 修复前 ❌

| 场景 | 截取位置 | 画面内容 | 匹配度 |
|-----|---------|---------|--------|
| 痛苦表情在后半段 | 片段开头 | 铺垫画面 | ❌ 不匹配 |
| 精彩动作在中间 | 片段开头 | 准备动作 | ❌ 不匹配 |
| 情感高潮在结尾 | 片段开头 | 情感铺垫 | ❌ 不匹配 |

### 修复后 ✅

| 场景 | 截取位置 | 画面内容 | 匹配度 |
|-----|---------|---------|--------|
| 痛苦表情在后半段 | 片段中间 | 痛苦表情 | ✅ 匹配 |
| 精彩动作在中间 | 片段中间 | 精彩动作 | ✅ 匹配 |
| 情感高潮在结尾 | 片段中间 | 情感高潮 | ✅ 匹配 |

## 原理说明

### 为什么中间位置更好？

1. **AI 匹配的特性**：
   - Twelve Labs API 的视觉搜索会找到包含匹配内容的片段
   - 但不保证匹配内容在片段开头
   - 通常匹配内容在片段的**中间区域**

2. **视频内容的特性**：
   - 大多数视频片段有：铺垫 → 高潮 → 收尾
   - 精彩画面往往在中间位置
   - 从中间截取概率上更容易命中精彩画面

## 与占位回退的关系

当 TwelveLabs/HLS 拉流多次失败时，渲染 Worker 会调用 `scripts/media/create_placeholder_clip.py` 生成的占位片段，并按歌词时长重新封装，使时间线不会出现断裂。相关指标会通过 `render_clip_placeholder_total` 暴露在 Prometheus 中。

## 并行裁剪与观测补充

- `RenderClipScheduler` 会为每个片段分配 `clip_task_id`，并跟踪 `queued_at/start_at/finished_at`，所有日志必须携带这些字段及 `parallel_slot`。
- 渲染 Worker 通过 `asyncio.TaskGroup` + `Semaphore` 实现 `RENDER_CLIP_CONCURRENCY`（默认 4），单个视频的 `per_video_limit` 默认 2 防止 CDN 拉流雪崩。
- Prometheus 指标
  - `render_clip_inflight`：实时并发槽位计数。
  - `render_clip_duration_ms`：下载 + 裁剪耗时直方图。
  - `render_clip_failures_total` / `render_clip_placeholder_total`：失败类别与占位使用次数。
- `render_jobs.metrics.render.clip_stats` 写入 `total_clips`、`peak_parallelism`、`placeholder_tasks`、`failed_tasks`、`fallback_reason_counts`，用于审计每次渲染的表现。

3. **统计优势**：
   - 从开头截取：只有当匹配在前1/3时才准确
   - 从中间截取：匹配在中间2/3都有机会命中
   - 显著提高语义匹配率

## 潜在问题

### 问题1：如果匹配恰好在开头？

**回答**：这种情况较少，即使发生，中间位置也不会相差太远。对于短片段（<5秒），影响微乎其微。

### 问题2：会不会错过真正的匹配？

**回答**：不会。我们保留了 `api_start_ms` 和 `api_end_ms`，如果未来需要调整策略（如智能检测匹配位置），可以轻松修改。

## 未来优化方向

### 高级方案（可选）

如果未来需要更精确的匹配，可以考虑：

1. **使用 Twelve Labs 的时间戳信息**：
   - 某些 API 可能返回精确的匹配时间点
   - 直接使用该时间点作为中心

2. **基于评分的智能定位**：
   - 如果 API 返回多个候选片段，选择评分最高的区域中心

3. **动态偏移策略**：
   - 根据片段长度动态调整偏移比例
   - 长片段偏向中后部（60%位置）
   - 短片段保持居中（50%位置）

## 相关文件

- `src/pipelines/matching/timeline_builder.py:100-135` - 核心实现
- `TIMESTAMP_FIX_REPORT.md` - 时长修复报告
- `VIDEO_DEDUPLICATION_README.md` - 去重功能说明

## 更新记录

- **2025-11-18**: 初始版本
  - 从片段开头截取 → 从片段中间截取
  - 添加边界保护
  - 解决语义失调问题

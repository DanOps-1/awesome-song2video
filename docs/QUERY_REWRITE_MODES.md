# 查询改写模式说明

**版本**: v2.0
**最后更新**: 2025-12-16

---

## 概述

系统使用 **分数阈值模式** 进行智能查询改写，通过 `QUERY_REWRITE_SCORE_THRESHOLD` 配置项控制：

- 当原始查询的最高匹配分数低于阈值时，触发 DeepSeek 查询改写
- 改写后持续循环，直到分数达到阈值或达到最大尝试次数
- 默认阈值为 `1.0`（严格模式，确保最高质量匹配）

---

## 分数阈值机制

### 配置参数

```bash
# .env
QUERY_REWRITE_ENABLED=true           # 启用查询改写
QUERY_REWRITE_SCORE_THRESHOLD=1.0    # 分数阈值 (0.0-1.0)
QUERY_REWRITE_MAX_ATTEMPTS=3         # 最大改写次数
DEEPSEEK_API_KEY=sk-xxxxx            # DeepSeek API 密钥
```

### 执行流程

```
┌────────────────────────────────────────────────────────────────┐
│ 1. 原始查询 TwelveLabs                                         │
│    query = "我停在回忆"                                        │
│    candidates = search_segments(query, limit=20)              │
│    best_score = max(candidates.scores)                        │
└────────────────────┬───────────────────────────────────────────┘
                     │
                     ├─ best_score >= threshold? ──► 使用原始结果（成功）
                     │
                     └─ best_score < threshold? ──► 触发智能改写
                                │
        ┌───────────────────────┴───────────────────────────────┐
        │ 2. DeepSeek 查询改写循环（最多 max_attempts 次）        │
        │                                                        │
        │    attempt=0: 具体化视觉描述                           │
        │      "我停在回忆" → "一个人坐在窗边回忆往事的画面"       │
        │      → 搜索 → best_score >= threshold? → 退出循环      │
        │                                                        │
        │    attempt=1: 场景通用化                               │
        │      → "思念回忆的孤独氛围"                             │
        │      → 搜索 → best_score >= threshold? → 退出循环      │
        │                                                        │
        │    attempt=2: 极简关键词                               │
        │      → "回忆 孤独"                                      │
        │      → 搜索 → 返回最佳结果                              │
        └───────────────────────────────────────────────────────┘
```

### 分数阈值含义

| 阈值 | 说明 | 适用场景 |
|------|------|---------|
| `1.0` | 严格模式，分数必须达到 100% 才停止改写 | 追求最高匹配精度 |
| `0.9` | 高质量模式，90% 以上即可 | 平衡精度与效率 |
| `0.8` | 标准模式 | 一般场景 |
| `0.7` | 宽松模式 | 快速匹配，允许一定误差 |
| `0.0` | 禁用改写，直接使用原始查询结果 | 测试/调试 |

---

## 改写策略演进

每次改写尝试使用不同的提示词策略：

### Attempt 0: 具体化视觉描述
```
输入: "我停在回忆"
输出: "一个人坐在窗边，看着窗外的雨滴，回忆往事的画面"
特点: 将抽象情感转化为具体可视化场景
```

### Attempt 1: 场景通用化
```
输入: "我停在回忆"
输出: "思念、回忆、孤独的氛围"
特点: 提取核心情感关键词，扩大匹配范围
```

### Attempt 2: 极简关键词
```
输入: "我停在回忆"
输出: "回忆 孤独 窗边"
特点: 最简化关键词，最大化匹配可能
```

---

## 日志示例

### 原始查询分数达标
```json
{
  "event": "timeline_builder.candidates",
  "text_preview": "一个人在街上走",
  "count": 15,
  "best_score": 0.95,
  "threshold": 0.9,
  "action": "use_original"
}
```

### 触发改写
```json
{
  "event": "timeline_builder.score_below_threshold",
  "original": "我停在回忆",
  "best_score": 0.65,
  "threshold": 0.9,
  "message": "分数低于阈值，触发查询改写"
}
```

### 改写成功
```json
{
  "event": "timeline_builder.rewrite_success",
  "original": "我停在回忆",
  "attempt": 1,
  "final_query": "一个人坐在窗边回忆往事的画面",
  "best_score": 0.92,
  "count": 15
}
```

### 改写达到最大次数
```json
{
  "event": "timeline_builder.rewrite_exhausted",
  "original": "我停在回忆",
  "attempts": 3,
  "best_score": 0.78,
  "message": "达到最大改写次数，使用最佳结果"
}
```

---

## 推荐配置

### 生产环境（高质量）
```bash
QUERY_REWRITE_ENABLED=true
QUERY_REWRITE_SCORE_THRESHOLD=1.0   # 严格模式
QUERY_REWRITE_MAX_ATTEMPTS=3
```

### 平衡模式（节省 API 调用）
```bash
QUERY_REWRITE_ENABLED=true
QUERY_REWRITE_SCORE_THRESHOLD=0.9   # 90% 即可
QUERY_REWRITE_MAX_ATTEMPTS=2
```

### 测试/开发环境
```bash
QUERY_REWRITE_ENABLED=false         # 禁用改写
# 或
QUERY_REWRITE_SCORE_THRESHOLD=0.0   # 永不改写
```

---

## API 成本分析

假设一首歌 **50 句歌词**：

### 场景 1: 原始查询全部达标
| 阈值 | TwelveLabs 调用 | DeepSeek 调用 | 总成本 |
|------|----------------|---------------|--------|
| 0.9 | 50 次 | 0 次 | 最低 |

### 场景 2: 50% 歌词需改写
| 阈值 | TwelveLabs 调用 | DeepSeek 调用 | 总成本 |
|------|----------------|---------------|--------|
| 0.9 | 75 次 | 25 次 | 中等 |
| 1.0 | 100 次 | 50 次 | 较高 |

### 场景 3: 抽象歌词（全部需改写）
| 阈值 | TwelveLabs 调用 | DeepSeek 调用 | 总成本 |
|------|----------------|---------------|--------|
| 0.9 | 100 次 | 50 次 | 较高 |
| 1.0 | 150 次 | 100+ 次 | 最高 |

**结论**: 阈值设置需根据歌词类型和成本预算权衡。

---

## 监控指标

### Prometheus
```promql
# 改写触发率
sum(rate(query_rewrite_triggered_total[5m])) /
sum(rate(query_search_total[5m]))

# 平均改写次数
avg(query_rewrite_attempts)
```

### Loki 日志查询
```logql
# 统计改写成功
{job="lyrics-mix-worker"}
  |= "timeline_builder.rewrite_success"
  | json

# 查看低分数触发
{job="lyrics-mix-worker"}
  |= "timeline_builder.score_below_threshold"
  | json
  | line_format "{{.original}} score={{.best_score}}"
```

---

## 常见问题

### Q1: 阈值设为 1.0 是否会导致无限循环？

**A**: 不会。系统有 `QUERY_REWRITE_MAX_ATTEMPTS` 限制（默认 3 次），达到最大次数后会使用当前最佳结果。

### Q2: 如何动态调整阈值？

**A**: 修改 `.env` 文件后重启服务，或通过环境变量覆盖：
```bash
QUERY_REWRITE_SCORE_THRESHOLD=0.85 python -m uvicorn src.api.main:app
```

### Q3: 分数是如何计算的？

**A**: 分数来自 TwelveLabs API 的语义匹配置信度，范围 0.0-1.0，表示查询与视频片段的语义相似程度。

### Q4: 旧的 QUERY_REWRITE_MANDATORY 配置还能用吗？

**A**: 已废弃。请改用 `QUERY_REWRITE_SCORE_THRESHOLD`：
- 旧 `MANDATORY=true` → 新 `THRESHOLD=1.0`
- 旧 `MANDATORY=false` → 新 `THRESHOLD=0.0`（或合适的阈值）

---

**文档结束**

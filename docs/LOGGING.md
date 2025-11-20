# 日志系统说明

## 概述

系统使用 `structlog` 提供结构化日志功能，支持同时输出到控制台和文件，便于调试和问题排查。

## 日志文件

### 位置

所有日志文件保存在项目根目录的 `logs/` 目录下：

- **`logs/app.log`** - 所有级别的日志（INFO 及以上）
- **`logs/error.log`** - 错误日志（WARNING 及以上）

### 轮转策略

日志文件自动轮转，防止磁盘空间占满：

- 单个文件最大: 10MB
- 保留备份数: 5 个
- 命名格式: `app.log`, `app.log.1`, `app.log.2`, ..., `app.log.5`

总存储空间：约 60MB（2 个文件 × 6 个版本 × 10MB）

## 日志格式

### 文件格式（JSON）

日志文件使用 JSON 格式，每行一条日志记录，便于程序分析：

```json
{
  "event": "twelvelabs.search_query",
  "query": "A person running",
  "base_url": "default",
  "options": ["visual", "audio"],
  "timestamp": "2025-11-20T08:26:47.601116Z",
  "level": "info"
}
```

### 控制台格式

- **终端环境**：彩色格式化输出，便于人类阅读
- **非终端环境**（如管道、重定向）：JSON 格式，便于程序处理

## 使用方法

### 在代码中记录日志

```python
import structlog

logger = structlog.get_logger(__name__)

# 基础日志
logger.info("user_login", user_id=123, username="alice")

# 警告日志
logger.warning("rate_limit_approaching", remaining=10, limit=100)

# 错误日志
logger.error("api_request_failed", status_code=500, endpoint="/api/search")

# 异常日志
try:
    result = risky_operation()
except Exception as e:
    logger.exception("operation_failed", operation="risky_operation")
```

### 查看日志

#### 实时查看所有日志

```bash
tail -f logs/app.log | jq .
```

#### 实时查看错误日志

```bash
tail -f logs/error.log | jq .
```

#### 过滤特定事件

```bash
# 查看所有 TwelveLabs 搜索查询
cat logs/app.log | jq 'select(.event == "twelvelabs.search_query")'

# 查看视频去重日志
cat logs/app.log | jq 'select(.event == "twelvelabs.skip_duplicate_video")'

# 查看查询改写日志
cat logs/app.log | jq 'select(.event == "query_rewriter.rewritten")'
```

#### 统计日志

```bash
# 统计各类事件数量
cat logs/app.log | jq -r '.event' | sort | uniq -c | sort -rn

# 统计错误类型
cat logs/error.log | jq -r '.event' | sort | uniq -c | sort -rn

# 按时间范围过滤
cat logs/app.log | jq 'select(.timestamp >= "2025-11-20T08:00:00Z" and .timestamp <= "2025-11-20T09:00:00Z")'
```

#### 分析性能

```bash
# 查看渲染任务耗时
cat logs/app.log | jq 'select(.event == "render_worker.clip_task_end") | {video_id, duration_ms}'

# 统计平均裁剪耗时
cat logs/app.log | jq 'select(.event == "render_worker.clip_task_end") | .duration_ms' | \
  awk '{sum+=$1; count++} END {print "平均:", sum/count, "ms"}'
```

#### 追踪特定请求

```bash
# 通过 mix_id 追踪完整流程
cat logs/app.log | jq 'select(.mix_id == "c56595c6-d7a4-4ff3-af68-4e280dd1aebb")'

# 通过 job_id 追踪渲染任务
cat logs/app.log | jq 'select(.job_id == "4bd09870-0a7c-4795-9617-4ce672bfe083")'
```

## 常用日志事件

### TwelveLabs API

| Event | 说明 | 级别 |
|-------|------|------|
| `twelvelabs.client_initialized` | 客户端初始化 | INFO |
| `twelvelabs.search_query` | 搜索查询 | INFO |
| `twelvelabs.raw_item` | API 返回的原始结果 | INFO |
| `twelvelabs.skip_duplicate_video` | 跳过重复视频 | DEBUG |
| `twelvelabs.search_failed` | 搜索失败 | WARNING |
| `twelvelabs.retrieve_success` | 视频检索成功 | INFO |

### 查询改写

| Event | 说明 | 级别 |
|-------|------|------|
| `query_rewriter.rewritten` | 查询改写完成 | INFO |
| `query_rewriter.failed` | 改写失败 | WARNING |

### Timeline 构建

| Event | 说明 | 级别 |
|-------|------|------|
| `timeline_builder.mandatory_rewrite` | 强制改写模式 | INFO |
| `timeline_builder.candidates` | 候选片段数量 | INFO |
| `timeline_builder.diversity_selection` | 去重选择 | INFO |
| `timeline_builder.reuse_segment` | 重复使用片段 | WARNING |

### 渲染 Worker

| Event | 说明 | 级别 |
|-------|------|------|
| `render_worker.started` | 渲染任务开始 | INFO |
| `render_worker.clip_task_start` | 片段裁剪开始 | INFO |
| `render_worker.clip_task_end` | 片段裁剪完成 | INFO |
| `render_worker.completed` | 渲染任务完成 | INFO |

## 日志级别

- **DEBUG**: 调试信息（默认不输出到文件）
- **INFO**: 常规信息
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

## 配置

日志配置位于 `src/infra/observability/otel.py` 的 `configure_logging()` 函数中。

如需修改日志级别、文件大小等参数，请编辑该文件。

## 注意事项

1. **日志文件不会自动删除**，需要定期清理或依赖轮转机制
2. **敏感信息**：请勿在日志中记录密码、API 密钥等敏感信息
3. **性能考虑**：大量日志输出可能影响性能，生产环境建议只记录 INFO 及以上
4. **日志备份**：重要生产环境建议定期备份日志文件到远程存储

## 故障排查示例

### 查找渲染失败原因

```bash
# 查看所有错误
cat logs/error.log | jq .

# 查看特定 job 的错误
cat logs/error.log | jq 'select(.job_id == "YOUR_JOB_ID")'
```

### 查找重复视频问题

```bash
# 统计跳过的重复视频
cat logs/app.log | jq 'select(.event == "twelvelabs.skip_duplicate_video")' | jq -r '.video_id' | sort | uniq -c | sort -rn

# 查看某个视频被跳过的所有记录
cat logs/app.log | jq 'select(.event == "twelvelabs.skip_duplicate_video" and .video_id == "691dec6e1804eb3adc585940")'
```

### 分析 TwelveLabs API 性能

```bash
# 查看所有搜索查询
cat logs/app.log | jq 'select(.event == "twelvelabs.search_query") | {query: .query, options: .options}'

# 统计每个查询返回的结果数
cat logs/app.log | jq 'select(.event == "timeline_builder.candidates") | {text: .text_preview, count: .count}'
```

## 进阶用法

### 与 Loki 集成

如果使用 Grafana Loki 进行日志聚合，可以使用 Promtail 采集日志：

```yaml
# promtail-config.yaml
scrape_configs:
  - job_name: lyrics-mix
    static_configs:
      - targets:
          - localhost
        labels:
          job: lyrics-mix
          __path__: /path/to/twelve_labs/logs/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            event: event
            timestamp: timestamp
```

### 与 ELK Stack 集成

JSON 格式的日志可以直接导入 Elasticsearch：

```bash
# 使用 Filebeat 采集
filebeat.inputs:
  - type: log
    enabled: true
    paths:
      - /path/to/twelve_labs/logs/app.log
    json.keys_under_root: true
    json.add_error_key: true
```

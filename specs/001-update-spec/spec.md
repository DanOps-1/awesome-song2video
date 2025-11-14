# 功能规格：需求与实现对齐更新

**特性分支**：`001-update-spec`  
**创建日期**：2025-11-13  
**状态**：Draft  
**输入**：用户描述 “根据代码更新需求”

> 所有内容必须以简体中文撰写，且描述需直接映射到可测试的异步实现。禁止只写概念或英文引用。

## 用户场景与测试（必填）

> 用户故事需按重要性排序，并满足“独立可上线、独立可测试”的切片标准。

### 用户故事 1 - 策划可查看完整时间线清单（优先级：P1）

策划人员在审核混剪任务前，需要一次性获取每句歌词对应的视频片段、起止时间与置信度，以便在正式渲染前确认语义与节奏；该数据必须通过 JSON manifest API 返回，并同时提供结构化的对齐指标，方便与 UI 对接或导入到其他审核工具。

**优先级理由**：没有跨端可读的 manifest，就无法在线下审核或复核代码输出，T1 优先解决。

**独立测试方式**：调用 `GET /api/v1/mixes/{mix_id}/preview` 并核对返回结构，确保清单覆盖全部歌词句，字段齐全，且同时写入 `SongMixRequest.metrics.preview`。

**验收场景**：

1. **Given** 混剪任务已生成时间线，**When** 调用 preview API，**Then** 返回的 manifest 与 `metrics.preview` 记录所有歌词行及对应片段信息。
2. **Given** 某句歌词缺少 TwelveLabs 候选，**When** 调用 preview API，**Then** manifest 标识 fallback 片段并提示需人工补片。

---

### 用户故事 2 - 渲染质量可量化追踪（优先级：P2）

运维/质量负责人需要在每次渲染完成后查看字幕与画面对齐偏差、平均/最大延迟等指标，并确保数据写入 RenderJob 记录与结构化日志中，以便在监控平台绘图或制定 SLA。

**优先级理由**：没有可量化指标就无法判断交付物是否满足 SC-003，且无法在故障时溯源。

**独立测试方式**：提交渲染任务，完成后读取 `GET /api/v1/mixes/{mix_id}/render?job_id=...` 和数据库 `render_jobs.metrics`，确认指标字段写入、数值合理，并在日志中存在 `preview/render` 对齐信息。

**验收场景**：

1. **Given** 渲染任务完成，**When** 查询 RenderJob，**Then** `metrics.render` 中包含 `line_count/avg_delta_ms/max_delta_ms/total_duration_ms` 且数值 > 0。
2. **Given** 发生字幕对齐超阈值，**When** 读取日志，**Then** 可看到对应 mix_id 和 delta 值以便报警。

---

### 用户故事 3 - 媒资 fallback 与上传缺失可追踪（优先级：P3）

媒资管理员需要在 TwelveLabs 未命中或对象存储不可用时，及时了解系统使用的 fallback 视频、写入的本地路径与“尚未完成 MinIO 集成”的 TODO 记录，以便后续补齐素材或恢复上传功能。

**优先级理由**：fallback 素材缺失会导致最终视频出现空画面，必须有可视化告警与操作指引。

**独立测试方式**：将某些歌词刻意设为无候选或关闭 MinIO，运行 demo/渲染流程，验证日志与 manifest 中显示 fallback 来源，并在 `metrics.preview` 里统计缺失句数。

**验收场景**：

1. **Given** 缺少 TwelveLabs 命中，**When** 生成时间线，**Then** manifest 对应行标记 fallback 视频 ID，`metrics.preview` 记录缺失统计。
2. **Given** MinIO 未启动，**When** 渲染完成，**Then** 日志记录 `render_worker.storage_todo` 并写出本地产物路径，方便人工处理。

---

### 边界条件

- 当 TwelveLabs 无候选时，系统必须生成 fallback manifest 项并提示需要人工补片。
- 当 fallback 视频文件缺失时，系统必须输出 warning 并允许渲染继续，以免阻塞整体流程。
- 当对象存储不可用时，系统必须在日志中记录 TODO，并将输出文件保留在本地路径供后续处理。

## 需求（必填）

### 功能性需求

- **FR-001**：系统必须提供 `GET /api/v1/mixes/{mix_id}/preview` 接口，返回包含全部歌词句的 JSON manifest（字段含 line_id、lyrics、source_video_id、clip_start_ms、clip_end_ms、confidence、fallback 标记）。
- **FR-002**：系统必须在生成 manifest 时计算 `metrics.preview`（行数、总时长、平均/最大字幕-画面时长差、fallback 句数）并持久化到 `SongMixRequest.metrics.preview`。
- **FR-003**：系统必须在每次渲染完成后写入 `RenderJob.metrics.render`（包含 line_count、avg_delta_ms、max_delta_ms、total_duration_ms）、日志记录对齐结果，并通过 API 返回。
- **FR-004**：系统必须在渲染流程中对未上传到对象存储的产物输出 `render_worker.storage_todo` 日志，并暴露本地文件路径供人工回收。
- **FR-005**：系统必须在 manifest 与渲染日志中清晰标识 fallback 视频 ID 与缺失原因，确保媒资管理员能够在 1 个工作日内补齐素材。
- **FR-006**：系统必须限制同时渲染任务数（默认 3 个）并在日志中记录排队情况，以便后续调优。
- **FR-007**：系统必须将 preview/render 指标同步到 observability 平台（通过现有 OTEL + Prometheus/Loki outbox），使其可在仪表盘内查看。

### 核心实体

- **PreviewManifestEntry**：描述单句歌词与匹配片段的映射，字段包含 line_id、line_no、lyrics、source_video_id、clip_start_ms、clip_end_ms、confidence、fallback 标记。
- **PreviewMetrics**：存放在 `SongMixRequest.metrics.preview` 中的统计数据（line_count、total_duration_ms、avg_delta_ms、max_delta_ms、fallback_count、generated_at）。
- **RenderMetrics**：存放在 `RenderJob.metrics.render` 中的渲染对齐数据（line_count、avg_delta_ms、max_delta_ms、total_duration_ms、queued_at、finished_at）。

## 成功标准（必填）

- **SC-001**：100% 已生成时间线的混剪任务都能在 2 秒内返回完整 manifest，并写入 `metrics.preview`。
- **SC-002**：95% 的渲染任务报告 `avg_delta_ms ≤ 200` 且 `max_delta_ms ≤ 400`，异常任务自动记录日志供报警。
- **SC-003**：所有 fallback 事件都在 manifest 与日志中标记，且管理员可在 1 个工作日内定位缺失素材（通过日志中提供的本地路径）。
- **SC-004**：运维可在仪表盘观察 preview/render 指标，并在 5 分钟内看到最新任务的数据采集。

## 假设与依赖

- MinIO/S3 暂未启用，短期内以内存+本地文件方式保存渲染结果；当对象存储上线时需复用同一指标与日志方案。
- OTEL Collector 与 Prometheus/Loki 已部署，预留了 `lyrics_preview_*`、`render_alignment_*` 指标命名空间。
- 策划审核仍在外部前端执行，本需求仅交付 API 与指标；前端消费 manifest 的行为由另一迭代实现。

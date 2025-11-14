# Phase 0 研究：歌词语义混剪视频

## 研究项 1：歌词时间戳与语音对齐策略

- **Decision**：采用 WebVTT/LRC 导入优先，若缺失则通过 Whisper large-v3（离线推理）生成时间戳，再以 Pydub 进行句子级能量切分，保证在 30 秒内输出初版时间线。
- **Rationale**：Whisper large-v3 在中英歌词场景 WER < 8%，推理耗时对 3 分钟音频约 15 秒（GPU 模式）；结合 Pydub 可在无准确分句时快速校正，满足 FR-001 时效要求。
- **Alternatives considered**：
  - **Google Speech-to-Text**：需外部 API，成本高且存在数据出境合规风险。
  - **Julius/kaldi 离线模型**：部署复杂，中文表现逊于 Whisper。

## 研究项 2：TwelveLabs Python SDK 的异步封装方式

- **Decision**：继续使用官方 `twelvelabs` SDK（同步），在服务层使用 `anyio.to_thread.run_sync` 包裹阻塞调用；对批量查询采用 `asyncio.gather` + 自定义速率限制器（Redis token bucket）。
- **Rationale**：SDK 内建鉴权与分页逻辑，保持兼容官方更新；通过线程池封装可满足宪章的异步要求，同时速率限制可避免 API 配额耗尽。
- **Alternatives considered**：
  - **直接使用 httpx 调 TwelveLabs REST**：需要自行维护签名与 pagination，并失去 SDK 内建的 index schema 校验。
  - **封装独立微服务**：增加部署复杂度，当前需求量尚可由单体完成。

## 研究项 3：视频渲染与字幕叠加方案

- **Decision**：使用 FFmpeg CLI 进行无损拼接与字幕绘制；由渲染 worker 生成中间 EDL(JSON) → FFmpeg filtergraph 脚本，再通过 `asyncio.create_subprocess_exec` 驱动；字幕采用 `ASS` 模板以保证逐句高亮。
- **Rationale**：FFmpeg 对海量素材拼接和滤镜具备成熟能力，可在 CPU/GPU 上工作；ASS 模板能实现歌词逐句高亮同步，满足 SC-003；现有团队已有 FFmpeg 经验。
- **Alternatives considered**：
  - **MoviePy**：纯 Python 但在 1080p/多段拼接时易产生性能瓶颈。
  - **Shotstack/云渲染服务**：需额外费用且数据需上传外部，存在版权与网络延迟风险。

## 研究项 4：数据存储与并发控制

- **Decision**：时间线、任务状态、日志主数据存放 PostgreSQL（SQLModel 建模）；Redis 用于幂等锁、任务排队与速率限制；对象存储使用内部 MinIO（S3 兼容）管理原始视频与输出作品。
- **Rationale**：PostgreSQL 支持复杂查询与 JSONB，可存储 LyricLine/VideoSegmentMatch；Redis 内置 Lua 脚本可实现匹配请求节流；MinIO 可部署在私有云，满足版权与内网带宽要求。
- **Alternatives considered**：
  - **MongoDB**：JSON 文档友好但与现有团队栈不符且缺少强事务。
  - **本地文件系统**：难以扩展且缺少访问控制。

## 研究项 5：监控指标与质量守护

- **Decision**：采用 OpenTelemetry + OTLP Collector，将 API/worker trace、metrics 写入 Prometheus + Loki；关键指标包括 `lyrics_parse_latency`, `match_hit_rate`, `render_duration`, `api_error_rate`；同时引入 Golden 视频测试集，每日对比帧差异。
- **Rationale**：满足宪章原则五的结构化日志与可观测性要求；Golden 测试可防止渲染滤镜改动导致字幕错位。
- **Alternatives considered**：
  - **仅使用 print/日志**：无法关联 trace_id，与原则五冲突。
  - **商业 APM**：需额外预算，先采用开源链路。

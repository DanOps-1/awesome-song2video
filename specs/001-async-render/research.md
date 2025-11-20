# Phase 0 Research — 渲染 Worker 并行异步裁剪

## R1 配置热加载机制
- **Decision**：使用 Redis Pub/Sub 频道 `render:config` 广播配置（`render_clip_concurrency`、重试阈值、占位策略），render worker 在启动时创建后台 `asyncio.Task` 订阅该频道，收到消息后即刻更新内存态并写入结构化日志。
- **Rationale**：Redis 已在项目中作为 Arq 依赖存在，无需新增组件；Pub/Sub 延迟 < 100ms，能满足“无需重启即可生效”的需求；实现中可重用 `redis_pool`，只要监听一个频道即可。
- **Alternatives considered**：
  1. 轮询 `.env` 或数据库配置——需周期性 IO 且延迟不可控，修改方式复杂。
  2. 通过 Arq `enqueue_job` 发送控制任务——耦合任务队列，若 queue 堵塞则配置无法及时生效。

## R2 占位片段素材
- **Decision**：提供统一的 3 秒黑屏 + 500Hz beep 的 MP4 文件 `media/fallback/clip_placeholder.mp4`，格式 H.264 + AAC，与现有输出容器一致。Worker 在 clip 最终失败时复制该文件并通过 FFmpeg 重新封装（以对齐时间）。
- **Rationale**：固定文件便于 CDN、测试和合规校验；3 秒可覆盖大多数歌词行的最短窗口；与现有音视频设置相符，避免额外转码。
- **Alternatives considered**：
  1. 动态生成纯黑画面——需要在运行期调用 FFmpeg/pygame，增加 CPU 和复杂度。
  2. 直接在最终 concat 阶段插入静音音轨——无法覆盖视频轨，且难以对齐字幕。

## R3 TwelveLabs HLS 并行裁剪最佳实践
- **Decision**：
  - 将全球并发限制在 `min(render_clip_concurrency, 6)`，并在 `_stream_cache` 中保存 retrieve 结果，避免重复请求。
  - 对同一 `video_id` 建立每视频 `asyncio.Semaphore(2)` 防止同源突发。
  - 结合现有 `with_rate_limit`（40 req/min）在 retrieve 之前加 500ms 抖动，减少瞬时冲击。
- **Rationale**：与 TwelveLabs 文档建议（<=10 并发/索引）一致；缓存 stream URL 可以将 retrieve API 调用削减 60% 以上；per-video 限制减少 HLS keyframe 冲突，保证 FFmpeg 开始处于关键帧附近。
- **Alternatives considered**：
  1. 仅依赖 token bucket 不做 per-video 限制——高重复请求时依旧容易被 CDN 429。
  2. 预下载整段 MP4 再切割——违反“按需截取”约束且占用磁盘。

## R4 TaskGroup + FFmpeg 并行模式
- **Decision**：在 `_extract_clips` 中创建 `asyncio.TaskGroup`，每个任务调用 `asyncio.to_thread(_cut_clip, ...)`；通过独立的 `asyncio.Semaphore` 控制线程池并发；任务生命周期内打点日志并写入 Prometheus Gauge `render_clip_inflight`。
- **Rationale**：TaskGroup 能确保异常向上冒泡并在最终 `await` 时统一处理；`to_thread` 可复用 Python 解释器线程而无需自建进程池；配合 Semaphore 可避免一次性创建过多 FFmpeg 进程。
- **Alternatives considered**：
  1. `asyncio.create_subprocess_exec` 直接运行 FFmpeg——对 HLS `-ss` 定位不稳定且日志采集较复杂。
  2. 使用多进程池——需要序列化上下文，且进程启动成本更高。

# 更新日志

## 2025-12-30

### 技术改进

#### TwelveLabs SDK 规范化升级 🔧
- **SDK 调用规范化**：
  - 将 `self._client: Any` 改为 `self._client: TwelveLabs`，明确类型注解
  - 使用 SDK 官方异常类型替代通用 `Exception` 捕获
  - 所有异常类型直接从 `twelvelabs` 模块导入
- **精细化异常处理**：
  - `ForbiddenError`：API 认证失败，记录 ERROR 日志并抛出 RuntimeError
  - `TooManyRequestsError`：频率限制，记录 WARNING 日志并触发 failover
  - `BadRequestError`：请求参数错误，记录 WARNING 日志并返回空列表
  - `NotFoundError`：资源未找到，记录 WARNING 日志并返回空列表
  - `InternalServerError`：服务端错误，记录 ERROR 日志并触发 failover
- **类型提示改进**：
  - 使用 PEP 604 语法 `int | None` 替代 `Optional[int]`
  - 使用 PEP 585 语法 `list[str]` 替代 `List[str]`
  - 移除不必要的 `Any` 类型导入
- **影响文件**：
  - `src/services/matching/twelvelabs_client.py` - 核心客户端
  - `src/services/matching/action_detector.py` - 视频动作分析
  - `src/retrieval/twelvelabs/retriever.py` - 检索器类型优化

### 验证结果

- ✅ 所有 80 个单元测试通过
- ✅ Ruff 代码检查通过
- ✅ mypy 类型检查通过

---

## 2025-12-14

### 新增功能

#### 1. 视频比例选择功能 🎬
- **用户可选输出比例**：支持 16:9（默认）和 4:3 输出视频
- **智能视频处理**：使用模糊背景方式处理不同比例的视频，保持视频完整显示
- **前后端完整实现**：用户界面可选择视频比例，后端自动处理

#### 2. 双语字幕支持 🌐
- **中英双语字幕**：支持同时显示中文和英文字幕
- **用户可选功能**：双语字幕改为用户可选，默认仅显示原文
- **免费翻译 API**：添加免费翻译 API 作为备选方案

#### 3. 实时日志查看（管理后台）📋
- **日志查看 API**：新增 `/api/v1/admin/logs` 系列接口
  - `GET /logs` - 查询历史日志，支持关键词和级别过滤
  - `GET /logs/stream` - 实时日志流（Server-Sent Events）
  - `GET /logs/files` - 列出可用日志文件
- **前端日志查看器**：`web/src/pages/system/LogViewer.tsx`
  - 实时日志流显示
  - 关键词过滤和级别筛选
  - 快捷过滤按钮（beat, render, timeline, error, warning）
  - 自动滚动和手动控制

#### 4. 节拍分析 API 🎵
- **节拍分析接口**：`POST /api/v1/mixes/{id}/analyze-beats` - 手动触发节拍分析
- **获取节拍数据**：`GET /api/v1/mixes/{id}/beats` - 获取已分析的节拍数据
- **卡点功能开关**：`PATCH /api/v1/mixes/{id}/beat-sync` - 启用/禁用卡点功能
- **数据持久化**：新增 `BeatAnalysisData` 和 `VideoActionCache` 数据模型

#### 5. 智能查询改写优化 🤖
- **基于分数阈值的智能改写**：
  - 原始搜索 score >= 0.9 → 跳过改写（直白歌词不被干扰）
  - 原始搜索 score < 0.9 → 触发改写 → 对比选择更好的结果
  - 新配置项：`QUERY_REWRITE_SCORE_THRESHOLD`（默认 0.9）
- **Tom and Jerry 专属优化**：查询改写提示词针对卡通素材库定制
- **三阶段策略**：
  - 策略 0：卡通场景转换（猫鼠追逐、躲藏、打斗等可视化场景）
  - 策略 1：动作强化模式（通用卡通动作关键词）
  - 策略 2：极简兜底（确保能搜到卡通画面）
- **示例改写**：`"Hunt you down eat you alive"` → `"cat chasing and catching mouse"`

### Bug 修复

#### 1. 视频去重优化 🔧
- **问题**：视频去重逻辑在某些情况下导致相同视频被重复使用
- **修复**：使用随机选择替代固定 fallback，提升去重效果

#### 2. 字幕相关修复 📝
- 修复字幕文件扩展名（.ass）
- 调整字幕大小为 40px（折中值）
- 缩小字幕边距，减少对画面的遮挡

#### 3. 视频比例处理 📐
- 使用模糊背景方式处理视频比例，保持视频完整显示
- 修正视频比例缩放问题，避免黑边填充

#### 4. 用户体验改进 ✨
- generated 状态下移除删除按钮，添加返回修改歌词按钮
- 放宽歌曲名称长度限制到 500 字符
- 改进错误提示，显示后端具体错误信息
- start.sh 总是重启后端确保加载最新代码
- start.sh 使用 venv 中的 Python 命令

### 文件变更

**新增文件**：
- `src/api/v1/routes/admin/logs.py` - 日志查看 API
- `src/api/v1/routes/beat_analysis.py` - 节拍分析 API
- `src/audio/beat_detector.py` - 节拍检测模块
- `src/domain/models/beat_sync.py` - 节拍同步数据模型
- `web/src/pages/system/LogViewer.tsx` - 日志查看前端页面

**修改文件**：
- `src/workers/render_worker.py` - 支持视频比例、双语字幕
- `src/api/main.py` - 注册新路由
- `src/api/v1/routes/admin/__init__.py` - 导出日志路由
- `frontend/src/pages/Status.tsx` - 添加比例选择、双语字幕选项
- `web/src/components/Sidebar.tsx` - 添加日志查看入口

---

## 2025-12-13

### 新增功能

#### 1. 鼓点自动卡点（类似剪映）🎵
- **新增鼓点检测模块**：`src/audio/onset_detector.py`
  - 使用 librosa onset_detect 检测音频实际鼓点/冲击点
  - 支持从视频音频中提取鼓点
  - 计算最佳偏移使音乐鼓点与视频鼓点对齐
- **两种卡点模式**：
  - `action` 模式：视频画面动作点 → 音乐节拍（旧模式）
  - `onset` 模式：视频音频鼓点 → 音乐鼓点（新模式，默认）
- **配置项**：
  - `BEAT_SYNC_MODE=onset|action` - 选择卡点模式
  - `BEAT_SYNC_ONSET_TOLERANCE_MS=80` - 鼓点对齐容差

#### 2. 视频候选容错增强 🛡️
- **候选数量从 3 个增加到 5 个**：提高渲染时的容错性
- **渲染阶段自动回退**：当一个候选视频裁剪失败时，自动尝试下一个

### Bug 修复

#### 1. 禁止视频循环播放 🚫
- **问题**：当视频时长 < 歌词时长时，之前会循环播放视频
- **修复**：严格丢弃时长不足的候选，确保画面连贯性
- **影响文件**：
  - `src/pipelines/matching/timeline_builder.py` - 匹配阶段过滤
  - `src/services/matching/twelvelabs_video_fetcher.py` - 渲染阶段检查

#### 2. 修复 Fallback 视频时间错误 🔧
- **问题**：Fallback 视频使用歌词时间（如 120000ms）而非视频时间
- **修复**：Fallback 统一从 0 开始裁剪，长度等于所需时长
- **影响**：所有 fallback 场景（间隙填充、Outro、候选全过滤）

#### 3. 完善渲染候选回退日志 📝
- **新增**：当 `fetch_clip` 返回 None 时记录详细日志
- **事件**：`render_worker.candidate_clip_failed`
- **信息**：视频ID、时间范围、失败原因、是否继续尝试

### 文件变更

**新增文件**：
- `src/audio/onset_detector.py` - 鼓点检测模块

**修改文件**：
- `src/services/matching/beat_aligner.py` - 添加 `calculate_onset_alignment()` 方法
- `src/infra/config/settings.py` - 添加 `beat_sync_mode`、`beat_sync_onset_tolerance_ms` 配置
- `src/workers/timeline_worker.py` - 集成鼓点检测步骤
- `src/pipelines/matching/timeline_builder.py` - 添加鼓点对齐选择、修复 fallback 时间
- `src/services/matching/twelvelabs_video_fetcher.py` - 禁止循环、删除 `_cut_clip_with_loop`
- `src/workers/render_worker.py` - 完善候选回退日志

---

## 2025-11-20

### 新增功能

#### 1. 日志系统 🆕
- **自动日志保存**：所有日志自动保存到 `logs/` 目录
  - `logs/app.log` - 所有日志（JSON 格式）
  - `logs/error.log` - 错误日志（WARNING 及以上）
- **自动轮转**：单文件 10MB，保留 5 个备份，总空间约 60MB
- **双输出模式**：
  - 控制台：终端彩色输出 / 非终端 JSON 输出
  - 文件：统一 JSON 格式
- **自动初始化**：在 API、Worker、Demo 脚本中自动配置
- 详见：[docs/LOGGING.md](./docs/LOGGING.md)

#### 2. 视频去重优化 🆕
- **修复重复画面问题**：添加视频级别去重，同一视频只使用一次
- **智能选择**：优先使用 rank 最高的片段
- **日志追踪**：添加 `twelvelabs.skip_duplicate_video` 日志事件
- **实现位置**：`src/services/matching/twelvelabs_client.py:169-236`

### 技术改进

#### TwelveLabs API 理解
- **clarified `group_by="clip"` 行为**：
  - 返回扁平化片段列表
  - `clips` 字段为 `None`（不需要嵌套）
  - `start/end` 在 item 顶层
  - `clips_count=0` 是正常现象
- **clarified `group_by="video"` 行为**：
  - 返回按视频分组结果
  - `video_id` 在顶层为 `None`
  - 所有片段在 `clips` 数组中

### 文件变更

**新增文件**：
- `docs/LOGGING.md` - 日志系统完整文档
- `logs/.gitkeep` - 保持日志目录结构
- `scripts/dev/test_logging.py` - 日志功能测试
- `scripts/dev/verify_logging.py` - 日志配置验证
- `scripts/dev/test_group_by.py` - TwelveLabs group_by 参数测试
- `scripts/dev/debug_duplicate_videos.py` - 重复视频调试工具
- `CHANGELOG.md` - 本文件

**修改文件**：
- `src/infra/observability/otel.py` - 添加文件日志支持
- `src/api/main.py` - 自动调用 `configure_logging()`
- `src/workers/__init__.py` - Worker 启动时自动配置日志
- `scripts/dev/run_audio_demo.py` - Demo 脚本自动配置日志
- `src/services/matching/twelvelabs_client.py` - 添加视频去重逻辑
- `.gitignore` - 忽略日志文件但保留目录
- `README.md` - 添加日志系统说明

### Bug 修复

- ✅ 修复 `clips_count=0` 误解（这是正常行为）
- ✅ 修复重复视频画面问题（添加 video_id 去重）
- ✅ 修复日志未保存问题（自动调用配置）
- ✅ **修复 null 时间戳导致的一模一样画面问题** 🔥
  - 问题：TwelveLabs API 返回 start/end 为 null，旧代码默认为 0，导致多个片段都是 0-1000ms
  - 解决：跳过 null 时间戳的结果，记录警告日志
  - 影响：彻底解决"完全一模一样的画面"问题

### 已知问题

- ⚠️ TwelveLabs API 在某些查询下会返回 null 时间戳（已通过跳过处理）

### 下一步计划

- [ ] 添加日志查询工具（按时间、事件类型过滤）
- [ ] 集成 Loki/ELK 等日志聚合系统
- [ ] 添加日志告警机制（错误率阈值）

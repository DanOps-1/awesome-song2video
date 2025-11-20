# 更新日志

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

### 已知问题

无

### 下一步计划

- [ ] 添加日志查询工具（按时间、事件类型过滤）
- [ ] 集成 Loki/ELK 等日志聚合系统
- [ ] 添加日志告警机制（错误率阈值）

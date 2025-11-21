# 调试用短音频使用指南

## 问题

每次测试都要处理完整的 3 分钟音频（`tom.mp3`），调试效率低下。

## 解决方案

使用 20 秒的调试音频 `tom_debug_20s.mp3` 快速测试。

## 使用方法

### 1. 准备调试音频（首次使用）

```bash
# 在项目根目录下运行
./scripts/dev/prepare_debug_audio.sh
```

这会创建 `media/audio/tom_debug_20s.mp3`（440KB，20秒）

### 2. 运行调试测试

```bash
# 本地测试
python scripts/dev/run_audio_demo_debug.py
```

```bash
# 服务器测试
cd /root/autodl-tmp/awsome-song2video
source .venv/bin/activate
python scripts/dev/run_audio_demo_debug.py
```

## 对比

| 项目 | 完整音频 | 调试音频 | 提升 |
|------|---------|---------|------|
| 文件大小 | 3.9 MB | 440 KB | **9x 更小** |
| 时长 | 183 秒 | 20 秒 | **9x 更快** |
| 歌词行数 | ~50 行 | ~5 行 | **10x 更少** |
| 渲染时间 | ~2-3 分钟 | ~15-20 秒 | **6-9x 更快** |

## 适用场景

✅ **适合调试:**
- 测试候选片段回退逻辑
- 测试 SDK 集成
- 测试 FFmpeg 参数调整
- 测试错误处理
- 快速验证代码修改

❌ **不适合:**
- 性能压力测试
- 完整功能验收测试
- 最终质量检查

## 文件位置

```
media/audio/
├── tom.mp3              # 完整音频（3分钟）- 用于正式测试
└── tom_debug_20s.mp3    # 调试音频（20秒）- 用于快速调试
```

## 服务器部署

将调试音频和脚本推送到服务器：

```bash
# 本地提交
git add media/audio/tom_debug_20s.mp3
git add scripts/dev/run_audio_demo_debug.py
git add scripts/dev/prepare_debug_audio.sh
git commit -m "feat: 添加 20 秒调试音频用于快速测试"
git push

# 服务器拉取
cd /root/autodl-tmp/awsome-song2video
git pull
```

如果服务器上音频文件未同步（.gitignore），可以手动创建：

```bash
cd /root/autodl-tmp/awsome-song2video
./scripts/dev/prepare_debug_audio.sh
```

## 示例输出

```
========================================
启动调试测试 (20秒音频)
========================================

2025-11-21T06:00:00.000000Z [info] render_worker.started job_id=xxx
2025-11-21T06:00:15.000000Z [info] render_worker.completed job_id=xxx

========================================
调试测试完成！
========================================
Mix ID: abc-123
Job ID: xyz-789
输出视频: artifacts/render/output.mp4
音频时长: 20 秒
========================================

✓ 视频生成成功: artifacts/render/output.mp4
  文件大小: 12.34 MB
```

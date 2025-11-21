#!/bin/bash
# 准备调试用的 20 秒音频

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

AUDIO_DIR="$PROJECT_ROOT/media/audio"
SOURCE_AUDIO="$AUDIO_DIR/tom.mp3"
DEBUG_AUDIO="$AUDIO_DIR/tom_debug_20s.mp3"

echo "========================================"
echo "准备调试音频"
echo "========================================"

if [ ! -f "$SOURCE_AUDIO" ]; then
    echo "错误: 未找到源音频文件: $SOURCE_AUDIO"
    exit 1
fi

echo "源音频: $SOURCE_AUDIO"
echo "输出: $DEBUG_AUDIO"
echo ""

# 裁剪前 20 秒
ffmpeg -y -i "$SOURCE_AUDIO" -t 20 -c copy "$DEBUG_AUDIO" 2>&1 | grep -E "(Duration|size=)" || true

if [ -f "$DEBUG_AUDIO" ]; then
    echo ""
    echo "✓ 调试音频创建成功!"
    ls -lh "$DEBUG_AUDIO"

    # 检查时长
    DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$DEBUG_AUDIO")
    echo "时长: ${DURATION} 秒"
else
    echo "✗ 创建失败"
    exit 1
fi

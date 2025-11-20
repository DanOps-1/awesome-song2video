#!/usr/bin/env python3
"""分析选中片段的重复情况。"""

import json
import sys

# 收集所有 selected_clip
clips = []
for line in sys.stdin:
    try:
        data = json.loads(line)
        if data.get('event') == 'timeline_builder.selected_clip':
            clips.append({
                'video_id': data.get('video_id'),
                'start': data.get('start_ms'),
                'end': data.get('end_ms'),
                'index': data.get('index')
            })
    except:
        pass

# 按句子分组（每3个 clip 为一句）
print('选中的片段分析：')
print('=' * 80)

# 追踪所有已使用的片段
all_used = {}

for i in range(0, len(clips), 3):
    sentence_clips = clips[i:i+3]
    print(f'\n第 {i//3 + 1} 句：')

    for clip in sentence_clips:
        start_sec = clip['start'] / 1000
        end_sec = clip['end'] / 1000
        print(f"  [{clip['index']}] video={clip['video_id']}, {start_sec:.2f}s-{end_sec:.2f}s")

        # 检查是否与之前的片段重复
        video_id = clip['video_id']
        start_ms = clip['start']
        end_ms = clip['end']

        # 检查精确匹配
        key = (video_id, start_ms, end_ms)
        if key in all_used:
            print(f"    ❌ 完全重复！在第 {all_used[key]} 句已使用")

        # 检查时间重叠
        for used_key, sentence_num in all_used.items():
            used_vid, used_start, used_end = used_key
            if used_vid == video_id:
                # 计算重叠
                overlap_start = max(start_ms, used_start)
                overlap_end = min(end_ms, used_end)
                overlap = max(0, overlap_end - overlap_start)

                if overlap > 0:
                    shorter_duration = min(end_ms - start_ms, used_end - used_start)
                    overlap_ratio = overlap / shorter_duration if shorter_duration > 0 else 0
                    if overlap_ratio > 0:
                        print(f"    ⚠️ 时间重叠 {overlap_ratio*100:.1f}% 与第 {sentence_num} 句 ({used_start/1000:.2f}s-{used_end/1000:.2f}s)")

        all_used[key] = i//3 + 1

    # 检查是否有重复的 video_id
    video_ids = [c['video_id'] for c in sentence_clips]
    if len(video_ids) != len(set(video_ids)):
        print('  ⚠️ 警告：同一句中有重复的 video_id！')

print('\n' + '=' * 80)
print(f'总共分析了 {len(clips)} 个片段，{len(clips)//3} 句歌词')

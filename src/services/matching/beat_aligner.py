"""节拍对齐计算服务。

提供视频片段与音乐节拍的对齐评分计算，
用于优化视频选择和渲染时的时间微调。

支持两种对齐模式：
1. 动作对齐（旧）：视频画面动作点 → 音乐节拍
2. 鼓点对齐（新）：视频音频鼓点 → 音乐鼓点（类似剪映自动卡点）
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from src.audio.beat_detector import BeatAnalysisResult, find_nearest_beat
from src.audio.onset_detector import (
    OnsetResult,
    detect_onsets,
    detect_onsets_from_video,
    get_relative_onsets,
    find_best_offset,
)
from src.services.matching.action_detector import VideoActionProfile
from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class AlignmentScore:
    """对齐评分结果。"""

    score: float  # 总分 (0-1)
    best_action_point_ms: int | None  # 最佳动作点时间
    best_beat_ms: int | None  # 最匹配的节拍时间
    offset_ms: int  # 需要调整的偏移量（正值表示视频需要提前）
    details: dict[str, Any]  # 评分细节


class BeatAligner:
    """节拍与动作对齐计算器。"""

    def __init__(
        self,
        max_adjustment_ms: int | None = None,
        action_weight: float | None = None,
        beat_weight: float | None = None,
    ) -> None:
        """初始化对齐计算器。

        Args:
            max_adjustment_ms: 最大允许调整的时间偏移（毫秒）
            action_weight: 动作点评分权重
            beat_weight: 节拍对齐评分权重
        """
        settings = get_settings()
        self.max_adjustment_ms = (
            max_adjustment_ms
            if max_adjustment_ms is not None
            else settings.beat_sync_max_adjustment_ms
        )
        self.action_weight = (
            action_weight
            if action_weight is not None
            else settings.beat_sync_action_weight
        )
        self.beat_weight = (
            beat_weight if beat_weight is not None else settings.beat_sync_beat_weight
        )

    def calculate_alignment_score(
        self,
        candidate: dict[str, Any],
        lyric_start_ms: int,
        beats: BeatAnalysisResult | None,
        video_profile: VideoActionProfile | None,
    ) -> AlignmentScore:
        """计算候选片段与节拍的对齐分数。

        评分考虑：
        1. 片段内是否有动作高光点
        2. 动作点与歌词起始节拍的接近程度
        3. 视频原始评分

        Args:
            candidate: 视频候选片段信息
            lyric_start_ms: 歌词行起始时间（毫秒）
            beats: 音频节拍分析结果
            video_profile: 视频动作分析档案

        Returns:
            AlignmentScore 包含评分和建议的调整偏移
        """
        clip_start_ms = int(candidate.get("start_time_ms", 0))
        clip_end_ms = int(candidate.get("end_time_ms", 0))
        original_score = float(candidate.get("score", 0.0))

        # 默认值
        target_beat_ms: int | None = None
        best_action_ms: int | None = None
        suggested_offset = 0
        action_score = 0.0
        beat_score = 0.0

        # 如果没有节拍数据，只返回原始分数
        if beats is None:
            return AlignmentScore(
                score=original_score,
                best_action_point_ms=None,
                best_beat_ms=None,
                offset_ms=0,
                details={
                    "original_score": original_score,
                    "action_score": 0.0,
                    "beat_score": 0.0,
                    "alignment_bonus": 0.0,
                    "reason": "no_beat_data",
                },
            )

        # 找到歌词起始位置最近的节拍
        beat_result = find_nearest_beat(beats, lyric_start_ms, self.max_adjustment_ms)
        if beat_result:
            target_beat_ms = beat_result[0]
            beat_offset = beat_result[1]
            # 节拍分数：偏移越小分数越高
            beat_score = 1.0 - (abs(beat_offset) / self.max_adjustment_ms)
        else:
            target_beat_ms = lyric_start_ms

        # 计算动作对齐分数
        if video_profile and video_profile.action_points:
            # 找到片段内的所有动作点
            actions_in_clip = [
                ap
                for ap in video_profile.action_points
                if clip_start_ms <= ap.timestamp_ms < clip_end_ms
            ]

            if actions_in_clip:
                # 找到与目标节拍最接近的动作点
                # 目标：让动作点对齐到歌词起始的节拍
                best_action = min(
                    actions_in_clip,
                    key=lambda ap: abs(
                        (ap.timestamp_ms - clip_start_ms)
                        - (target_beat_ms - lyric_start_ms)
                    ),
                )
                best_action_ms = best_action.timestamp_ms

                # 计算需要的偏移量
                # 动作点在片段内的相对位置
                action_relative_ms = best_action_ms - clip_start_ms
                # 节拍在歌词内的相对位置
                beat_relative_ms = target_beat_ms - lyric_start_ms

                # 偏移量 = 动作相对位置 - 节拍相对位置
                # 正值意味着动作点比节拍晚，需要把视频提前
                suggested_offset = action_relative_ms - beat_relative_ms

                # 限制偏移范围
                suggested_offset = max(
                    -self.max_adjustment_ms,
                    min(self.max_adjustment_ms, suggested_offset),
                )

                # 动作分数 = 动作置信度 * 对齐精度
                alignment_precision = 1.0 - (
                    abs(suggested_offset) / self.max_adjustment_ms
                )
                action_score = best_action.confidence * alignment_precision

        # 综合评分
        alignment_bonus = (
            self.action_weight * action_score + self.beat_weight * beat_score
        )

        # 最终分数 = 原始分数 * 0.7 + 对齐加成 * 0.3
        final_score = original_score * 0.7 + alignment_bonus * 0.3

        return AlignmentScore(
            score=final_score,
            best_action_point_ms=best_action_ms,
            best_beat_ms=target_beat_ms,
            offset_ms=suggested_offset,
            details={
                "original_score": original_score,
                "action_score": action_score,
                "beat_score": beat_score,
                "alignment_bonus": alignment_bonus,
                "clip_start_ms": clip_start_ms,
                "clip_end_ms": clip_end_ms,
                "actions_found": (
                    len(video_profile.action_points) if video_profile else 0
                ),
            },
        )

    def adjust_clip_timing(
        self,
        clip_start_ms: int,
        clip_end_ms: int,
        offset_ms: int,
        source_duration_ms: int | None = None,
    ) -> tuple[int, int]:
        """调整片段时间以实现卡点对齐。

        Args:
            clip_start_ms: 原始起始时间
            clip_end_ms: 原始结束时间
            offset_ms: 建议的调整偏移（正值表示视频需要提前）
            source_duration_ms: 源视频总时长（用于边界检查）

        Returns:
            (adjusted_start_ms, adjusted_end_ms)
        """
        duration = clip_end_ms - clip_start_ms

        # 应用偏移：正偏移意味着把视频提前播放
        new_start = clip_start_ms - offset_ms

        # 边界检查：不能小于 0
        if new_start < 0:
            new_start = 0

        # 边界检查：不能超出视频时长
        if source_duration_ms and new_start + duration > source_duration_ms:
            new_start = max(0, source_duration_ms - duration)

        new_end = new_start + duration

        if offset_ms != 0:
            logger.debug(
                "beat_aligner.timing_adjusted",
                original_start=clip_start_ms,
                new_start=new_start,
                offset=offset_ms,
                duration=duration,
            )

        return (new_start, new_end)

    def should_apply_beat_sync(
        self,
        beats: BeatAnalysisResult | None,
        min_stability: float = 0.5,
    ) -> bool:
        """判断是否应该应用节拍同步。

        对于节奏不稳定的音乐，卡点可能效果不好。

        Args:
            beats: 节拍分析结果
            min_stability: 最小稳定性阈值

        Returns:
            是否应该应用节拍同步
        """
        if beats is None:
            return False

        if len(beats.beat_times_ms) < 4:
            logger.info(
                "beat_aligner.skip_sync",
                reason="too_few_beats",
                beat_count=len(beats.beat_times_ms),
            )
            return False

        if beats.tempo_stability < min_stability:
            logger.info(
                "beat_aligner.skip_sync",
                reason="unstable_tempo",
                stability=beats.tempo_stability,
                threshold=min_stability,
            )
            return False

        return True


    async def calculate_onset_alignment(
        self,
        candidate: dict[str, Any],
        lyric_start_ms: int,
        lyric_end_ms: int,
        music_onsets: OnsetResult,
        video_stream_url: str | None = None,
    ) -> AlignmentScore:
        """基于鼓点的对齐计算（类似剪映自动卡点）。

        核心逻辑：
        1. 获取歌词时间段内的音乐鼓点
        2. 从视频音频中提取鼓点
        3. 计算最佳偏移使两者鼓点对齐

        Args:
            candidate: 视频候选片段信息
            lyric_start_ms: 歌词开始时间
            lyric_end_ms: 歌词结束时间
            music_onsets: 整首歌曲的鼓点检测结果
            video_stream_url: 视频流 URL（用于提取视频音频）

        Returns:
            AlignmentScore 包含评分和建议偏移
        """
        clip_start_ms = int(candidate.get("start_time_ms", 0))
        clip_end_ms = int(candidate.get("end_time_ms", 0))
        original_score = float(candidate.get("score", 0.0))

        # 获取歌词时间段内的音乐鼓点（相对时间）
        music_onsets_relative = get_relative_onsets(
            music_onsets, lyric_start_ms, lyric_end_ms
        )

        if not music_onsets_relative:
            logger.debug(
                "beat_aligner.no_music_onsets",
                lyric_start_ms=lyric_start_ms,
                lyric_end_ms=lyric_end_ms,
            )
            return AlignmentScore(
                score=original_score,
                best_action_point_ms=None,
                best_beat_ms=None,
                offset_ms=0,
                details={
                    "original_score": original_score,
                    "reason": "no_music_onsets_in_range",
                    "mode": "onset",
                },
            )

        # 从视频中提取鼓点
        video_onsets_relative: list[int] = []
        if video_stream_url:
            try:
                video_onsets = await detect_onsets_from_video(
                    video_stream_url,
                    start_ms=clip_start_ms,
                    end_ms=clip_end_ms,
                )
                # 转换为相对时间（相对于 clip_start_ms）
                video_onsets_relative = [
                    t - clip_start_ms for t in video_onsets.onset_times_ms
                ]
            except Exception as exc:
                logger.warning(
                    "beat_aligner.video_onset_extraction_failed",
                    video_url=video_stream_url[:50] if video_stream_url else None,
                    error=str(exc),
                )

        if not video_onsets_relative:
            logger.debug(
                "beat_aligner.no_video_onsets",
                clip_start_ms=clip_start_ms,
                clip_end_ms=clip_end_ms,
            )
            return AlignmentScore(
                score=original_score,
                best_action_point_ms=None,
                best_beat_ms=None,
                offset_ms=0,
                details={
                    "original_score": original_score,
                    "reason": "no_video_onsets",
                    "mode": "onset",
                },
            )

        # 找到最佳偏移
        best_offset, alignment_score = find_best_offset(
            music_onsets=music_onsets_relative,
            video_onsets=video_onsets_relative,
            max_offset_ms=self.max_adjustment_ms,
            step_ms=25,  # 更精细的步长
            tolerance_ms=80,  # 鼓点对齐容差
        )

        # 综合评分：原始分数 * 0.6 + 鼓点对齐分数 * 0.4
        final_score = original_score * 0.6 + alignment_score * 0.4

        logger.info(
            "beat_aligner.onset_alignment_calculated",
            video_id=candidate.get("source_video_id"),
            music_onsets=len(music_onsets_relative),
            video_onsets=len(video_onsets_relative),
            best_offset_ms=best_offset,
            alignment_score=round(alignment_score, 3),
            final_score=round(final_score, 3),
        )

        return AlignmentScore(
            score=final_score,
            best_action_point_ms=None,
            best_beat_ms=None,
            offset_ms=best_offset,
            details={
                "original_score": original_score,
                "onset_alignment_score": alignment_score,
                "music_onset_count": len(music_onsets_relative),
                "video_onset_count": len(video_onsets_relative),
                "mode": "onset",
            },
        )


# 单例实例
beat_aligner = BeatAligner()


async def analyze_music_onsets(
    audio_path: Path,
) -> OnsetResult:
    """分析整首歌曲的鼓点。

    在视频匹配开始前调用一次，结果缓存供所有歌词行使用。

    Args:
        audio_path: 音频文件路径

    Returns:
        OnsetResult 包含整首歌的鼓点时间
    """
    return await detect_onsets(audio_path)

"""音频节拍检测模块 - 基于 librosa 分析。

提供音乐节拍检测功能，用于实现画面与音乐的卡点对齐。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import librosa
import numpy as np
import structlog

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = structlog.get_logger(__name__)


@dataclass
class BeatAnalysisResult:
    """节拍分析结果。"""

    bpm: float  # 每分钟节拍数
    beat_times_ms: list[int]  # 节拍时间点（毫秒）
    downbeat_times_ms: list[int]  # 强拍时间点（毫秒）
    beat_strength: list[float]  # 每个节拍的强度
    tempo_stability: float  # 节奏稳定性 (0-1)


async def detect_beats(
    audio_path: Path,
    hop_length: int = 512,
    sr: int = 22050,
) -> BeatAnalysisResult:
    """检测音频中的节拍时间点。

    使用 librosa 的 beat_track 算法检测节拍，
    并计算每个节拍的强度用于后续对齐评分。

    Args:
        audio_path: 音频文件路径
        hop_length: FFT 跳跃长度
        sr: 采样率

    Returns:
        BeatAnalysisResult 包含 BPM 和节拍时间列表
    """
    import asyncio

    # 在线程池中加载音频（避免阻塞事件循环）
    def _load_and_analyze() -> tuple[float, NDArray, NDArray, NDArray]:
        y, sample_rate = librosa.load(audio_path.as_posix(), sr=sr)

        # 检测节拍
        tempo, beat_frames = librosa.beat.beat_track(
            y=y, sr=sample_rate, hop_length=hop_length
        )

        # 转换为时间
        beat_times = librosa.frames_to_time(
            beat_frames, sr=sample_rate, hop_length=hop_length
        )

        # 计算节拍强度（基于 onset strength）
        onset_env = librosa.onset.onset_strength(
            y=y, sr=sample_rate, hop_length=hop_length
        )

        return float(tempo), beat_times, beat_frames, onset_env

    tempo, beat_times, beat_frames, onset_env = await asyncio.to_thread(
        _load_and_analyze
    )

    # 转换为毫秒
    beat_times_ms = [int(t * 1000) for t in beat_times]

    # 提取节拍强度
    beat_strength = [
        float(onset_env[f]) for f in beat_frames if f < len(onset_env)
    ]

    # 估算强拍位置（假设 4/4 拍）
    downbeat_times_ms = _estimate_downbeats(beat_times_ms, tempo)

    # 计算节奏稳定性
    tempo_stability = _calculate_tempo_stability(beat_times_ms)

    logger.info(
        "beat_detector.analysis_complete",
        audio_path=audio_path.name,
        bpm=round(tempo, 1),
        beat_count=len(beat_times_ms),
        downbeat_count=len(downbeat_times_ms),
        stability=round(tempo_stability, 3),
    )

    return BeatAnalysisResult(
        bpm=tempo,
        beat_times_ms=beat_times_ms,
        downbeat_times_ms=downbeat_times_ms,
        beat_strength=beat_strength,
        tempo_stability=tempo_stability,
    )


def get_beats_in_range(
    beats: BeatAnalysisResult,
    start_ms: int,
    end_ms: int,
) -> list[int]:
    """获取指定时间范围内的节拍点。

    Args:
        beats: 节拍分析结果
        start_ms: 起始时间（毫秒）
        end_ms: 结束时间（毫秒）

    Returns:
        时间范围内的节拍时间点列表
    """
    return [t for t in beats.beat_times_ms if start_ms <= t < end_ms]


def find_nearest_beat(
    beats: BeatAnalysisResult,
    target_ms: int,
    max_offset_ms: int = 500,
) -> tuple[int, int] | None:
    """找到最接近目标时间的节拍点。

    Args:
        beats: 节拍分析结果
        target_ms: 目标时间（毫秒）
        max_offset_ms: 最大允许偏移（毫秒）

    Returns:
        (beat_time_ms, offset_ms) 或 None（如果没有足够接近的节拍）
    """
    if not beats.beat_times_ms:
        return None

    # 使用二分查找找最近的节拍
    beat_array = np.array(beats.beat_times_ms)
    idx = np.searchsorted(beat_array, target_ms)

    candidates = []
    if idx > 0:
        candidates.append(beat_array[idx - 1])
    if idx < len(beat_array):
        candidates.append(beat_array[idx])

    if not candidates:
        return None

    nearest = int(min(candidates, key=lambda t: abs(t - target_ms)))
    offset = nearest - target_ms

    if abs(offset) <= max_offset_ms:
        return (nearest, offset)
    return None


def find_nearest_downbeat(
    beats: BeatAnalysisResult,
    target_ms: int,
    max_offset_ms: int = 1000,
) -> tuple[int, int] | None:
    """找到最接近目标时间的强拍点。

    强拍通常用于更重要的卡点时刻。

    Args:
        beats: 节拍分析结果
        target_ms: 目标时间（毫秒）
        max_offset_ms: 最大允许偏移（毫秒）

    Returns:
        (downbeat_time_ms, offset_ms) 或 None
    """
    if not beats.downbeat_times_ms:
        return None

    downbeat_array = np.array(beats.downbeat_times_ms)
    idx = np.searchsorted(downbeat_array, target_ms)

    candidates = []
    if idx > 0:
        candidates.append(downbeat_array[idx - 1])
    if idx < len(downbeat_array):
        candidates.append(downbeat_array[idx])

    if not candidates:
        return None

    nearest = int(min(candidates, key=lambda t: abs(t - target_ms)))
    offset = nearest - target_ms

    if abs(offset) <= max_offset_ms:
        return (nearest, offset)
    return None


def _estimate_downbeats(beat_times_ms: list[int], bpm: float) -> list[int]:
    """估算强拍位置。

    假设 4/4 拍，每 4 拍的第一拍为强拍。

    Args:
        beat_times_ms: 节拍时间列表
        bpm: 每分钟节拍数

    Returns:
        强拍时间列表
    """
    if len(beat_times_ms) < 4:
        return beat_times_ms.copy()

    # 每 4 拍取第一拍作为强拍
    return beat_times_ms[::4]


def _calculate_tempo_stability(beat_times_ms: list[int]) -> float:
    """计算节奏稳定性。

    通过计算节拍间隔的变异系数来衡量稳定性。
    返回值越接近 1 表示节奏越稳定。

    Args:
        beat_times_ms: 节拍时间列表

    Returns:
        稳定性分数 (0-1)
    """
    if len(beat_times_ms) < 2:
        return 0.0

    intervals = np.diff(beat_times_ms)
    if len(intervals) == 0:
        return 0.0

    mean_interval = np.mean(intervals)
    if mean_interval == 0:
        return 0.0

    # 变异系数 = 标准差 / 平均值
    cv = np.std(intervals) / mean_interval

    # 转换为稳定性分数（变异系数越小越稳定）
    # cv=0 -> stability=1, cv>=1 -> stability~0
    stability = max(0.0, 1.0 - cv)

    return float(stability)


def get_beat_at_index(beats: BeatAnalysisResult, index: int) -> int | None:
    """获取指定索引的节拍时间。

    Args:
        beats: 节拍分析结果
        index: 节拍索引

    Returns:
        节拍时间（毫秒）或 None
    """
    if 0 <= index < len(beats.beat_times_ms):
        return beats.beat_times_ms[index]
    return None


def get_beat_interval_ms(beats: BeatAnalysisResult) -> float:
    """获取平均节拍间隔（毫秒）。

    Args:
        beats: 节拍分析结果

    Returns:
        平均节拍间隔
    """
    if beats.bpm <= 0:
        return 0.0
    return 60000.0 / beats.bpm

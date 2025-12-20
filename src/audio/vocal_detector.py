"""人声检测模块 - 基于 RMS 能量分析"""

from __future__ import annotations

import numpy as np
from pydub import AudioSegment
import structlog

logger = structlog.get_logger(__name__)


def detect_vocal_start(
    audio: AudioSegment,
    window_sec: float = 0.5,
    energy_percentile: int = 60,
) -> float:
    """基于音频能量检测人声开始位置，用于跳过纯音乐前奏。

    使用 RMS（均方根）能量分析检测音频中能量显著上升的位置，
    通常对应人声开始的时间点。

    Args:
        audio: pydub AudioSegment 音频片段
        window_sec: 分析窗口大小（秒），默认 0.5 秒
        energy_percentile: 能量阈值百分位数，默认 60

    Returns:
        人声开始的时间（秒），如果检测失败返回 0.0

    Example:
        >>> from pydub import AudioSegment
        >>> audio = AudioSegment.from_file("song.mp3")
        >>> vocal_start = detect_vocal_start(audio)
        >>> print(f"人声开始于: {vocal_start:.2f} 秒")
    """
    try:
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

        # 如果是立体声，转为单声道
        if audio.channels == 2:
            samples = samples.reshape((-1, 2)).mean(axis=1)

        # 计算每个窗口的 RMS 能量
        window_samples = int(window_sec * audio.frame_rate)
        num_windows = len(samples) // window_samples

        if num_windows < 2:
            return 0.0

        energies = []
        for i in range(num_windows):
            window = samples[i * window_samples : (i + 1) * window_samples]
            energy = np.sqrt(np.mean(window**2))  # RMS energy
            energies.append(energy)

        # 计算能量阈值
        energy_threshold = np.percentile(energies, energy_percentile)

        # 找到第一个超过阈值的窗口
        for i, energy in enumerate(energies):
            if energy > energy_threshold:
                vocal_start_sec = i * window_sec
                logger.info(
                    "vocal_detector.detected",
                    start_sec=vocal_start_sec,
                    energy=float(energy),
                    threshold=float(energy_threshold),
                )
                return vocal_start_sec

        return 0.0

    except Exception as e:
        logger.warning("vocal_detector.detection_failed", error=str(e))
        return 0.0


def calculate_rms_energy(audio: AudioSegment, window_sec: float = 0.5) -> list[float]:
    """计算音频的 RMS 能量曲线。

    Args:
        audio: pydub AudioSegment 音频片段
        window_sec: 分析窗口大小（秒）

    Returns:
        每个窗口的 RMS 能量值列表
    """
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).mean(axis=1)

    window_samples = int(window_sec * audio.frame_rate)
    num_windows = len(samples) // window_samples

    energies = []
    for i in range(num_windows):
        window = samples[i * window_samples : (i + 1) * window_samples]
        energy = float(np.sqrt(np.mean(window**2)))
        energies.append(energy)

    return energies

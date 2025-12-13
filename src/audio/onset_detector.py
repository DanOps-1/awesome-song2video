"""音频鼓点/起始点检测模块。

提供更精确的鼓点检测功能，用于实现类似剪映的自动卡点效果。
与 beat_detector 的区别：
- beat_detector: 检测音乐的节拍（规律性的拍子）
- onset_detector: 检测音频的起始点/鼓点（实际的声音冲击点）
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import librosa
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class OnsetResult:
    """鼓点检测结果。"""

    onset_times_ms: list[int]  # 鼓点时间点（毫秒）
    onset_strengths: list[float]  # 每个鼓点的强度
    duration_ms: int  # 音频总时长


async def detect_onsets(
    audio_path: Path,
    start_ms: int = 0,
    end_ms: int | None = None,
    hop_length: int = 512,
    sr: int = 22050,
) -> OnsetResult:
    """检测音频中的鼓点/起始点。

    使用 librosa 的 onset_detect 算法，比 beat_track 更精确地
    检测实际的声音冲击点（鼓点、乐器起始等）。

    Args:
        audio_path: 音频文件路径
        start_ms: 起始时间（毫秒），用于截取片段
        end_ms: 结束时间（毫秒），None 表示到结尾
        hop_length: FFT 跳跃长度
        sr: 采样率

    Returns:
        OnsetResult 包含鼓点时间列表和强度
    """

    def _analyze() -> tuple[list[float], list[float], int]:
        # 加载音频
        y, sample_rate = librosa.load(audio_path.as_posix(), sr=sr)
        duration_ms = int(len(y) / sample_rate * 1000)

        # 如果指定了时间范围，截取片段
        if start_ms > 0 or end_ms is not None:
            start_sample = int(start_ms * sample_rate / 1000)
            end_sample = int(end_ms * sample_rate / 1000) if end_ms else len(y)
            y = y[start_sample:end_sample]

        # 计算 onset envelope（能量包络）
        onset_env = librosa.onset.onset_strength(
            y=y, sr=sample_rate, hop_length=hop_length
        )

        # 检测 onset 时间点
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sample_rate,
            hop_length=hop_length,
            backtrack=True,  # 回溯到真正的起始点
        )

        # 转换为时间
        onset_times = librosa.frames_to_time(
            onset_frames, sr=sample_rate, hop_length=hop_length
        )

        # 提取每个 onset 的强度
        strengths = [float(onset_env[f]) for f in onset_frames if f < len(onset_env)]

        return list(onset_times), strengths, duration_ms

    onset_times, strengths, duration_ms = await asyncio.to_thread(_analyze)

    # 转换为毫秒，并加上起始偏移
    onset_times_ms = [int(t * 1000) + start_ms for t in onset_times]

    logger.debug(
        "onset_detector.analysis_complete",
        audio_path=audio_path.name,
        start_ms=start_ms,
        end_ms=end_ms,
        onset_count=len(onset_times_ms),
    )

    return OnsetResult(
        onset_times_ms=onset_times_ms,
        onset_strengths=strengths,
        duration_ms=duration_ms,
    )


async def detect_onsets_from_video(
    video_path: str,
    start_ms: int = 0,
    end_ms: int | None = None,
) -> OnsetResult:
    """从视频文件中提取音频并检测鼓点。

    Args:
        video_path: 视频文件路径或 URL（支持 HLS）
        start_ms: 起始时间（毫秒）
        end_ms: 结束时间（毫秒）

    Returns:
        OnsetResult 包含视频音频中的鼓点
    """
    # 创建临时音频文件
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_audio_path = Path(tmp.name)

    try:
        # 使用 FFmpeg 提取音频
        duration_sec = (end_ms - start_ms) / 1000 if end_ms else None
        start_sec = start_ms / 1000

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_sec),
        ]

        if duration_sec:
            cmd.extend(["-t", str(duration_sec)])

        cmd.extend([
            "-i", video_path,
            "-vn",  # 不要视频
            "-acodec", "pcm_s16le",
            "-ar", "22050",
            "-ac", "1",
            tmp_audio_path.as_posix(),
        ])

        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.warning(
                "onset_detector.ffmpeg_failed",
                video_path=video_path,
                stderr=result.stderr.decode()[:200],
            )
            return OnsetResult(onset_times_ms=[], onset_strengths=[], duration_ms=0)

        # 检测鼓点（从 0 开始，因为已经截取了片段）
        onsets = await detect_onsets(tmp_audio_path, start_ms=0, end_ms=None)

        # 将时间转换回原始视频时间
        adjusted_times = [t + start_ms for t in onsets.onset_times_ms]

        return OnsetResult(
            onset_times_ms=adjusted_times,
            onset_strengths=onsets.onset_strengths,
            duration_ms=onsets.duration_ms,
        )

    finally:
        # 清理临时文件
        if tmp_audio_path.exists():
            tmp_audio_path.unlink()


def get_onsets_in_range(
    onsets: OnsetResult,
    start_ms: int,
    end_ms: int,
) -> list[int]:
    """获取指定时间范围内的鼓点。

    Args:
        onsets: 鼓点检测结果
        start_ms: 起始时间（毫秒）
        end_ms: 结束时间（毫秒）

    Returns:
        时间范围内的鼓点时间列表
    """
    return [t for t in onsets.onset_times_ms if start_ms <= t < end_ms]


def get_relative_onsets(
    onsets: OnsetResult,
    start_ms: int,
    end_ms: int,
) -> list[int]:
    """获取指定时间范围内的鼓点（相对时间）。

    Args:
        onsets: 鼓点检测结果
        start_ms: 起始时间（毫秒）
        end_ms: 结束时间（毫秒）

    Returns:
        相对于 start_ms 的鼓点时间列表
    """
    absolute_onsets = get_onsets_in_range(onsets, start_ms, end_ms)
    return [t - start_ms for t in absolute_onsets]


def calculate_onset_alignment_score(
    music_onsets: list[int],
    video_onsets: list[int],
    tolerance_ms: int = 100,
) -> float:
    """计算两组鼓点的对齐分数。

    Args:
        music_onsets: 音乐鼓点（相对时间）
        video_onsets: 视频鼓点（相对时间）
        tolerance_ms: 容差范围（毫秒）

    Returns:
        对齐分数 (0-1)，1 表示完美对齐
    """
    if not music_onsets or not video_onsets:
        return 0.0

    matched = 0
    video_set = set(video_onsets)

    for m_onset in music_onsets:
        # 检查是否有视频鼓点在容差范围内
        for v_onset in video_set:
            if abs(m_onset - v_onset) <= tolerance_ms:
                matched += 1
                break

    # 分数 = 匹配数 / 音乐鼓点数
    return matched / len(music_onsets)


def find_best_offset(
    music_onsets: list[int],
    video_onsets: list[int],
    max_offset_ms: int = 500,
    step_ms: int = 50,
    tolerance_ms: int = 100,
) -> tuple[int, float]:
    """找到最佳的时间偏移，使视频鼓点与音乐鼓点对齐。

    Args:
        music_onsets: 音乐鼓点（相对时间）
        video_onsets: 视频鼓点（相对时间）
        max_offset_ms: 最大偏移范围（毫秒）
        step_ms: 搜索步长（毫秒）
        tolerance_ms: 对齐容差（毫秒）

    Returns:
        (best_offset_ms, best_score)
        - 正偏移表示视频需要提前（视频鼓点延后于音乐鼓点）
        - 负偏移表示视频需要延后（视频鼓点提前于音乐鼓点）
    """
    if not music_onsets or not video_onsets:
        return 0, 0.0

    best_offset = 0
    best_score = 0.0

    # 尝试不同的偏移量
    for offset in range(-max_offset_ms, max_offset_ms + 1, step_ms):
        # 将视频鼓点偏移
        shifted_video_onsets = [t + offset for t in video_onsets]

        # 计算对齐分数
        score = calculate_onset_alignment_score(
            music_onsets, shifted_video_onsets, tolerance_ms
        )

        if score > best_score:
            best_score = score
            best_offset = offset

    logger.debug(
        "onset_detector.best_offset_found",
        best_offset_ms=best_offset,
        best_score=round(best_score, 3),
        music_onset_count=len(music_onsets),
        video_onset_count=len(video_onsets),
    )

    return best_offset, best_score

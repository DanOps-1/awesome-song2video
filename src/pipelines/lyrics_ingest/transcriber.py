"""歌词转写与时间戳生成。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence, cast

from anyio import to_thread
from pydub import AudioSegment  # type: ignore[import-untyped]
import whisper  # type: ignore[import-untyped]
import structlog

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)

WhisperResult = dict[str, str | float | int | None]
WHISPER_MODEL = None

# 视频字幕叠加的常见文本模式（这些会导致 Whisper "锁定"）
CREDIT_PATTERNS = [
    r"^作词",
    r"^作曲",
    r"^词[\s:：]",
    r"^曲[\s:：]",
    r"^编曲",
    r"^制作",
    r"^监制",
    r"^演唱",
    r"李宗盛",  # 常见作词人
    r"林夕",
    r"方文山",
    r"周杰伦",
]


def _get_model() -> "whisper.Whisper":
    global WHISPER_MODEL  # noqa: PLW0603 - 需要缓存模型实例
    if WHISPER_MODEL is None:
        model_name = get_settings().whisper_model_name
        WHISPER_MODEL = whisper.load_model(model_name)
    return WHISPER_MODEL


def _is_credit_text(text: str) -> bool:
    """检查文本是否像视频字幕叠加（作词、作曲等）。"""
    text = text.strip()
    for pattern in CREDIT_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def _has_suspicious_gap(segments: list[dict], threshold_sec: float = 15.0) -> tuple[bool, float]:
    """检查识别结果是否有可疑的大间隙（说明可能漏掉了歌词）。

    返回: (是否有可疑间隙, 建议跳过的秒数)
    """
    if len(segments) < 2:
        return False, 0.0

    first_seg = segments[0]
    second_seg = segments[1] if len(segments) > 1 else None

    first_end = float(first_seg.get("end", 0))
    first_text = str(first_seg.get("text", "")).strip()

    # 检查第一个片段是否是字幕叠加
    if _is_credit_text(first_text):
        # 检查第一个片段后是否有大间隙
        if second_seg:
            second_start = float(second_seg.get("start", 0))
            gap = second_start - first_end
            if gap > threshold_sec:
                logger.info(
                    "transcriber.suspicious_gap_detected",
                    first_text=first_text,
                    first_end=first_end,
                    second_start=second_start,
                    gap=gap,
                    message="检测到字幕叠加后的大间隙，建议跳过重试",
                )
                # 建议跳过到第一个片段结束后 3 秒
                return True, first_end + 3.0

    return False, 0.0


def _filter_segments(segments: list[dict]) -> list[dict]:
    """过滤 Whisper 幻觉和低质量片段。"""
    settings = get_settings()
    filtered = []

    # 常见幻觉词表
    hallucination_phrases = [
        "优优独播剧场", "YoYo Television", "独播剧场",
        "字幕", "Copyright", "All rights reserved",
        "Thank you for watching", "Thanks for watching",
        "Amara.org", "Subtitles by",
        "未经作者授权", "禁止转载"
    ]

    for seg in segments:
        text = seg.get("text", "").strip()
        no_speech_prob = seg.get("no_speech_prob", 0.0)
        avg_logprob = seg.get("avg_logprob", 0.0)

        # 1. 检查非语音概率 (no_speech_prob)
        # 使用可配置的阈值
        # 阈值越低：过滤越严格，片段越多（但可能在长前奏歌曲中丢失开头人声）
        # 阈值越高：过滤越宽松，片段越少（但保留更多内容，包括长片段）
        if no_speech_prob > settings.whisper_no_speech_threshold:
            continue
            
        # 2. 检查平均对数概率 (avg_logprob)
        if avg_logprob < -1.0:
            continue
            
        # 3. 检查空文本
        if not text:
            continue
            
        # 4. 检查幻觉词
        is_hallucination = False
        for phrase in hallucination_phrases:
            if phrase.lower() in text.lower():
                is_hallucination = True
                break
        if is_hallucination:
            continue
            
        filtered.append(seg)
        
    return filtered


async def transcribe_with_timestamps(
    audio_path: Path,
    language: str | None = None,
    prompt: str | None = None,
    skip_intro: bool = False,  # 已废弃，保留参数兼容性
) -> Sequence[WhisperResult]:
    """使用 Whisper large-v3 模型输出句级时间戳。

    采用智能两遍扫描策略：
    1. 第一遍：正常转录
    2. 如果检测到字幕叠加（作词、作曲等）后有大间隙，说明 Whisper 被"锁定"了
    3. 第二遍：跳过字幕叠加部分重新转录
    4. 合并结果

    Args:
        audio_path: 音频文件路径
        language: 语言代码（如 "zh", "en"）
        prompt: Whisper initial_prompt
        skip_intro: 已废弃，不再使用
    """

    audio = AudioSegment.from_file(audio_path)
    audio_duration_sec = len(audio) / 1000.0

    temp = audio_path.with_suffix(".wav")
    audio.export(temp, format="wav")

    def _run_whisper(audio_segment: AudioSegment, temp_path: Path, offset_sec: float = 0.0) -> list[dict]:
        """运行 Whisper 并返回调整后的片段。"""
        audio_segment.export(temp_path, format="wav")
        model = _get_model()

        kwargs: dict = {"word_timestamps": True}
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["initial_prompt"] = prompt

        result = model.transcribe(temp_path.as_posix(), **kwargs)
        segments = list(result.get("segments", []))

        # 调整时间戳偏移
        if offset_sec > 0:
            for seg in segments:
                if "start" in seg:
                    seg["start"] = seg["start"] + offset_sec
                if "end" in seg:
                    seg["end"] = seg["end"] + offset_sec

        return segments

    def _run_model() -> Sequence[WhisperResult]:
        # === 第一遍：正常转录 ===
        logger.info("transcriber.first_pass", audio_path=str(audio_path))
        first_pass_segments = _run_whisper(audio, temp)

        # 检查是否有可疑间隙（字幕叠加导致的漏识别）
        has_gap, skip_to_sec = _has_suspicious_gap(first_pass_segments, threshold_sec=15.0)

        if not has_gap:
            # 没有可疑间隙，直接返回过滤后的结果
            clean_segments = _filter_segments(first_pass_segments)
            logger.info(
                "transcriber.first_pass_success",
                total_segments=len(first_pass_segments),
                clean_segments=len(clean_segments),
            )
            return cast(Sequence[WhisperResult], clean_segments)

        # === 第二遍：跳过字幕叠加部分重新转录 ===
        logger.info(
            "transcriber.second_pass",
            skip_to_sec=skip_to_sec,
            reason="检测到字幕叠加导致的歌词漏识别",
        )

        # 提取跳过后的音频
        skip_ms = int(skip_to_sec * 1000)
        remaining_audio = audio[skip_ms:]
        temp_skip = audio_path.parent / f"{audio_path.stem}_skip{int(skip_to_sec)}s.wav"

        second_pass_segments = _run_whisper(remaining_audio, temp_skip, offset_sec=skip_to_sec)
        temp_skip.unlink(missing_ok=True)

        # === 合并两遍结果 ===
        # 保留第一遍的字幕叠加片段（可能被过滤器过滤掉）
        # 加上第二遍的真实歌词
        merged_segments = []

        # 从第一遍保留 skip_to_sec 之前的片段
        for seg in first_pass_segments:
            seg_end = float(seg.get("end", 0))
            if seg_end <= skip_to_sec:
                merged_segments.append(seg)

        # 添加第二遍的所有片段
        merged_segments.extend(second_pass_segments)

        # 按时间排序并过滤
        merged_segments.sort(key=lambda x: float(x.get("start", 0)))
        clean_segments = _filter_segments(merged_segments)

        logger.info(
            "transcriber.two_pass_complete",
            first_pass_count=len(first_pass_segments),
            second_pass_count=len(second_pass_segments),
            merged_count=len(merged_segments),
            clean_count=len(clean_segments),
        )

        return cast(Sequence[WhisperResult], clean_segments)

    segments = await to_thread.run_sync(_run_model)
    temp.unlink(missing_ok=True)
    return segments

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

    检查前5个片段之间是否有大间隙，常见场景：
    1. 第一句歌词后有长间隙（说明中间歌词被漏掉了）
    2. 字幕叠加文本后有长间隙

    返回: (是否有可疑间隙, 建议跳过的秒数)
    """
    if len(segments) < 2:
        return False, 0.0

    # 检查前5个片段之间的间隙
    check_count = min(5, len(segments) - 1)
    for i in range(check_count):
        curr_seg = segments[i]
        next_seg = segments[i + 1]

        curr_end = float(curr_seg.get("end", 0))
        next_start = float(next_seg.get("start", 0))
        curr_text = str(curr_seg.get("text", "")).strip()

        gap = next_start - curr_end

        if gap > threshold_sec:
            logger.info(
                "transcriber.suspicious_gap_detected",
                segment_index=i,
                curr_text=curr_text,
                curr_end=curr_end,
                next_start=next_start,
                gap=gap,
                message="检测到大间隙，可能漏掉了歌词",
            )
            # 建议从当前片段结束后 1 秒开始重新扫描
            return True, curr_end + 1.0

    return False, 0.0


def _filter_segments(segments: list[dict], lenient: bool = False) -> list[dict]:
    """过滤 Whisper 幻觉和低质量片段。

    Args:
        segments: Whisper 原始片段列表
        lenient: 是否使用宽松模式（二次扫描时使用更低阈值）
    """
    settings = get_settings()
    filtered = []

    # 宽松模式使用更低的阈值（二次扫描时使用）
    threshold = 0.95 if lenient else settings.whisper_no_speech_threshold

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
        start_time = seg.get("start", 0)

        # 1. 检查非语音概率 (no_speech_prob)
        if no_speech_prob > threshold:
            logger.debug(
                "transcriber.segment_filtered",
                reason="no_speech_prob",
                text=text[:30],
                start=start_time,
                no_speech_prob=round(no_speech_prob, 3),
                threshold=threshold,
            )
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

    def _run_whisper(audio_segment: AudioSegment, temp_path: Path, offset_sec: float = 0.0, force_auto_lang: bool = False) -> list[dict]:
        """运行 Whisper 并返回调整后的片段。

        Args:
            force_auto_lang: 是否强制使用自动语言检测（二次扫描时使用，避免语言限制导致漏识别）
        """
        audio_segment.export(temp_path, format="wav")
        model = _get_model()

        kwargs: dict = {"word_timestamps": True}
        # 二次扫描时使用自动语言检测，避免因指定语言导致漏识别
        if language and not force_auto_lang:
            kwargs["language"] = language
        if prompt:
            kwargs["initial_prompt"] = prompt

        result = model.transcribe(temp_path.as_posix(), **kwargs)
        segments = list(result.get("segments", []))

        # 记录原始输出（前10个片段）
        for i, seg in enumerate(segments[:10]):
            logger.info(
                "transcriber.raw_segment",
                index=i,
                start=round(seg.get("start", 0) + offset_sec, 2),
                end=round(seg.get("end", 0) + offset_sec, 2),
                text=seg.get("text", "")[:40],
                no_speech_prob=round(seg.get("no_speech_prob", 0), 3),
                offset=offset_sec,
            )

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

        # === 第二遍：只提取间隙区域重新转录 ===
        # 找到间隙的结束位置（下一个有效片段的开始时间）
        gap_end_sec = skip_to_sec + 60  # 默认扫描60秒
        for seg in first_pass_segments:
            seg_start = float(seg.get("start", 0))
            if seg_start > skip_to_sec + 5:  # 找到间隙后的第一个片段
                gap_end_sec = seg_start + 5  # 多扫描5秒确保衔接
                break

        logger.info(
            "transcriber.second_pass",
            skip_to_sec=skip_to_sec,
            gap_end_sec=gap_end_sec,
            reason="检测到大间隙，只扫描间隙区域",
        )

        # 只提取间隙区域的音频（而不是整个剩余音频）
        skip_ms = int(skip_to_sec * 1000)
        gap_end_ms = int(gap_end_sec * 1000)
        gap_audio = audio[skip_ms:gap_end_ms]
        temp_skip = audio_path.parent / f"{audio_path.stem}_gap_{int(skip_to_sec)}_{int(gap_end_sec)}s.wav"

        # 二次扫描使用自动语言检测，避免因指定语言（如zh）导致跳过英文歌词
        second_pass_segments = _run_whisper(gap_audio, temp_skip, offset_sec=skip_to_sec, force_auto_lang=True)
        temp_skip.unlink(missing_ok=True)

        # === 合并两遍结果 ===
        merged_segments = []

        # 1. 从第一遍保留间隙之前的片段
        first_pass_before_gap = [
            seg for seg in first_pass_segments
            if float(seg.get("end", 0)) <= skip_to_sec
        ]
        merged_segments.extend(_filter_segments(first_pass_before_gap, lenient=False))

        # 2. 添加第二遍的间隙区域片段（宽松阈值）
        merged_segments.extend(_filter_segments(second_pass_segments, lenient=True))

        # 3. 从第一遍保留间隙之后的片段
        first_pass_after_gap = [
            seg for seg in first_pass_segments
            if float(seg.get("start", 0)) >= gap_end_sec - 5
        ]
        merged_segments.extend(_filter_segments(first_pass_after_gap, lenient=False))

        # 按时间排序去重
        merged_segments.sort(key=lambda x: float(x.get("start", 0)))

        logger.info(
            "transcriber.two_pass_complete",
            first_pass_count=len(first_pass_segments),
            second_pass_count=len(second_pass_segments),
            merged_count=len(merged_segments),
        )

        return cast(Sequence[WhisperResult], merged_segments)

    segments = await to_thread.run_sync(_run_model)
    temp.unlink(missing_ok=True)
    return segments

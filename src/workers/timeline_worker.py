"""歌词时间线 Worker。

两阶段工作流：
1. transcribe_lyrics: 只进行 Whisper 识别，生成歌词行 (pending -> transcribing -> transcribed)
2. match_videos: 对已确认的歌词进行视频匹配 (transcribed -> matching -> generated)
"""

from __future__ import annotations

import subprocess
import structlog

from pathlib import Path
from uuid import uuid4

from src.audio.structure_analyzer import (
    detect_intro_outro_boundaries,
    merge_intro_outro_lines,
)
from src.domain.models.song_mix import LyricLine, VideoSegmentMatch
from src.infra.config.settings import get_settings
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.pipelines.matching.timeline_builder import TimelineBuilder
from src.workers import BaseWorkerSettings

logger = structlog.get_logger(__name__)
repo = SongMixRepository()
builder = TimelineBuilder()


# 各语言防幻觉 Prompt 配置
LYRIC_PROMPTS = {
    "zh": "这是一首中文歌曲的歌词，请忽略背景音乐和非人声部分。",
    "en": "This is song lyrics, please ignore background music.",
    "ja": "これは歌詞です。背景音楽は無視してください。",
    "ko": "이것은 노래 가사입니다. 배경 음악은 무시해 주세요.",
    "es": "Esta es la letra de una canción, por favor ignora la música de fondo.",
    "fr": "Ce sont des paroles de chansons, veuillez ignorer la musique de fond.",
    "de": "Das ist ein Liedtext, bitte ignorieren Sie die Hintergrundmusik.",
}


def _get_audio_duration_ms(audio_path: Path) -> int:
    """使用 ffprobe 获取音频文件时长（毫秒）。"""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_path.as_posix(),
    ]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()) * 1000)
    except Exception as exc:
        logger.warning("ffprobe.audio_duration_failed", path=audio_path, error=str(exc))
    return 0


def _resolve_audio_path(audio_asset_id: str | None) -> Path | None:
    """从 audio_asset_id 解析出实际的音频文件路径。"""
    if not audio_asset_id:
        return None

    settings = get_settings()
    audio_dir = Path(settings.audio_asset_dir)

    # 查找匹配的文件（可能有不同后缀）
    for ext in [".mp3", ".wav", ".flac", ".m4a", ".aac"]:
        audio_file = audio_dir / f"{audio_asset_id}{ext}"
        if audio_file.exists():
            return audio_file

    # 尝试通配符匹配（文件名可能包含时间戳）
    matches = list(audio_dir.glob(f"{audio_asset_id}*"))
    if matches:
        return matches[0]

    logger.warning("audio_file_not_found", audio_asset_id=audio_asset_id)
    return None


async def transcribe_lyrics(ctx: dict | None, mix_id: str) -> None:
    """阶段1：只进行 Whisper 识别，生成歌词行供用户校对。

    状态流转: pending/transcribed -> transcribing -> transcribed
    支持重新识别：会自动清理旧的歌词数据。
    """
    logger.info("timeline_worker.transcribe_started", mix_id=mix_id)
    mix = await repo.get_request(mix_id)
    if mix is None:
        logger.warning("timeline_worker.mix_missing", mix_id=mix_id)
        return

    # 清理旧的歌词数据（支持重新识别）
    cleared_count = await repo.clear_lyrics(mix_id)
    if cleared_count > 0:
        logger.info("timeline_worker.old_lyrics_cleared", mix_id=mix_id, count=cleared_count)

    # 更新状态为 transcribing
    await repo.update_timeline_status(mix_id, "transcribing")
    await repo.update_timeline_progress(mix_id, 0.0)

    audio_path = _resolve_audio_path(mix.audio_asset_id)
    if not audio_path:
        logger.error("timeline_worker.audio_not_found", mix_id=mix_id)
        await repo.update_timeline_status(mix_id, "error")
        return

    # 处理语言
    req_language = getattr(mix, "language", "auto")
    whisper_language = None
    if req_language and req_language != "auto":
        whisper_language = req_language

    # 进度回调
    async def on_progress(progress: float) -> None:
        await repo.update_timeline_progress(mix_id, progress)
        logger.info(
            "timeline_worker.transcribe_progress", mix_id=mix_id, progress=round(progress, 1)
        )

    # 只进行 Whisper 识别
    segments = await builder.transcribe_only(
        audio_path=audio_path,
        language=whisper_language,
        on_progress=on_progress,
    )

    # 保存歌词行（不带视频候选）
    lines: list[LyricLine] = []
    for index, seg in enumerate(segments, start=1):
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start_ms = int(float(seg.get("start", 0)) * 1000)
        end_ms = int(float(seg.get("end", 0)) * 1000)
        lines.append(
            LyricLine(
                id=str(uuid4()),
                mix_request_id=mix_id,
                line_no=index,
                original_text=text,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                status="pending",  # 等待用户确认
            )
        )

    await repo.bulk_insert_lines(lines)
    await repo.update_timeline_status(mix_id, "transcribed")
    logger.info("timeline_worker.transcribe_completed", mix_id=mix_id, lines=len(lines))


async def match_videos(ctx: dict | None, mix_id: str) -> None:
    """阶段2：对已确认的歌词进行视频匹配。

    状态流转: transcribed -> matching -> generated
    前提条件: lyrics_confirmed = True

    增强功能：
    - 使用 allin1 分析音乐结构，检测 intro/outro
    - 合并开头的 credits 行为 (Intro)
    - 合并结尾的短行为 (Outro)
    - 边界以 API 歌词时间戳为准（ML 结果仅作参考）
    """
    logger.info("timeline_worker.match_started", mix_id=mix_id)
    mix = await repo.get_request(mix_id)
    if mix is None:
        logger.warning("timeline_worker.mix_missing", mix_id=mix_id)
        return

    if not mix.lyrics_confirmed:
        logger.warning("timeline_worker.lyrics_not_confirmed", mix_id=mix_id)
        return

    # 更新状态为 matching
    await repo.update_timeline_status(mix_id, "matching")
    await repo.update_timeline_progress(mix_id, 0.0)

    # 获取音频路径和时长
    audio_path = _resolve_audio_path(mix.audio_asset_id)
    audio_duration_ms = _get_audio_duration_ms(audio_path) if audio_path else 0

    # 获取已确认的歌词行
    existing_lines = await repo.list_lines(mix_id)
    if not existing_lines:
        logger.warning("timeline_worker.no_lyrics", mix_id=mix_id)
        await repo.update_timeline_status(mix_id, "error")
        return

    # 转换为统一格式
    lines_for_process = [
        {
            "text": line.original_text,
            "start_ms": line.start_time_ms,
            "end_ms": line.end_time_ms,
        }
        for line in existing_lines
    ]

    # ====== 检测 intro/outro 边界并合并 ======
    await repo.update_timeline_progress(mix_id, 5.0)

    # 基于歌词时长检测 intro/outro 边界
    # 规则：时长 >= 1秒 的歌词行被认为是"真正歌词"
    intro_end_ms, outro_start_ms = detect_intro_outro_boundaries(
        lyrics_lines=lines_for_process,
        audio_duration_ms=audio_duration_ms,
    )

    logger.info(
        "timeline_worker.boundaries_calculated",
        mix_id=mix_id,
        intro_end_ms=intro_end_ms,
        outro_start_ms=outro_start_ms,
        audio_duration_ms=audio_duration_ms,
    )

    # 合并 intro/outro 行
    merged_lines = merge_intro_outro_lines(
        lyrics_lines=lines_for_process,
        intro_end_ms=intro_end_ms,
        outro_start_ms=outro_start_ms,
        audio_duration_ms=audio_duration_ms,
    )

    logger.info(
        "timeline_worker.lines_merged",
        mix_id=mix_id,
        original_count=len(lines_for_process),
        merged_count=len(merged_lines),
    )

    await repo.update_timeline_progress(mix_id, 10.0)

    # ====== 进行视频匹配 ======
    async def on_progress(progress: float) -> None:
        # 进度范围: 10% - 90%
        adjusted_progress = 10.0 + progress * 0.8
        await repo.update_timeline_progress(mix_id, adjusted_progress)
        logger.info("timeline_worker.match_progress", mix_id=mix_id, progress=round(adjusted_progress, 1))

    result = await builder.match_videos_for_lines(
        lines=merged_lines,
        audio_duration_ms=audio_duration_ms,
        on_progress=on_progress,
    )

    # ====== 保存结果 ======
    await repo.update_timeline_progress(mix_id, 90.0)

    # 清理旧的歌词行（因为合并后数量可能变化）
    await repo.clear_lyrics(mix_id)

    # 保存合并后的歌词行和视频候选
    new_lines: list[LyricLine] = []
    for index, result_line in enumerate(result.lines, start=1):
        line_id = str(uuid4())

        new_line = LyricLine(
            id=line_id,
            mix_request_id=mix_id,
            line_no=index,
            original_text=result_line.text,
            start_time_ms=result_line.start_ms,
            end_time_ms=result_line.end_ms,
            status="matched",
            auto_confidence=result_line.candidates[0]["score"] if result_line.candidates else 0.0,
        )
        new_lines.append(new_line)

    # 批量插入歌词行
    await repo.bulk_insert_lines(new_lines)

    # 保存视频候选
    for new_line, result_line in zip(new_lines, result.lines):
        candidates: list[VideoSegmentMatch] = []
        for candidate in result_line.candidates:
            candidates.append(
                VideoSegmentMatch(
                    id=candidate["id"],
                    line_id=new_line.id,
                    source_video_id=candidate["source_video_id"],
                    index_id=get_settings().tl_index_id,
                    start_time_ms=candidate["start_time_ms"],
                    end_time_ms=candidate["end_time_ms"],
                    score=candidate["score"],
                    generated_by="auto",
                )
            )
        await repo.replace_candidates(new_line.id, candidates)

    await repo.update_timeline_progress(mix_id, 100.0)
    await repo.update_timeline_status(mix_id, "generated")
    logger.info(
        "timeline_worker.match_completed",
        mix_id=mix_id,
        original_lines=len(existing_lines),
        final_lines=len(new_lines),
    )


async def build_timeline(ctx: dict | None, mix_id: str) -> None:
    """完整构建流程（兼容旧代码）：Whisper 识别 + 视频匹配。

    注意：新流程应使用 transcribe_lyrics + match_videos 两阶段。
    """
    logger.info("timeline_worker.started", mix_id=mix_id)
    mix = await repo.get_request(mix_id)
    if mix is None:
        logger.warning("timeline_worker.mix_missing", mix_id=mix_id)
        return

    # 更新状态为 generating
    await repo.update_timeline_status(mix_id, "generating")
    await repo.update_timeline_progress(mix_id, 0.0)

    audio_path = _resolve_audio_path(mix.audio_asset_id)

    # 处理语言和 Prompt
    req_language = getattr(mix, "language", "auto")

    whisper_language = None
    prompt = None

    if req_language and req_language != "auto":
        whisper_language = req_language

    # 进度回调：将进度更新到数据库
    async def on_progress(progress: float) -> None:
        await repo.update_timeline_progress(mix_id, progress)
        logger.info("timeline_worker.progress", mix_id=mix_id, progress=round(progress, 1))

    result = await builder.build(
        audio_path=audio_path,
        lyrics_text=mix.lyrics_text,
        language=whisper_language,
        prompt=prompt,
        on_progress=on_progress,
    )

    lines: list[LyricLine] = []
    candidates: list[VideoSegmentMatch] = []
    for index, line in enumerate(result.lines, start=1):
        line_id = str(uuid4())
        lines.append(
            LyricLine(
                id=line_id,
                mix_request_id=mix_id,
                line_no=index,
                original_text=line.text,
                start_time_ms=line.start_ms,
                end_time_ms=line.end_ms,
                auto_confidence=(line.candidates[0]["score"] if line.candidates else 0.0),
            )
        )
        for candidate in line.candidates:
            candidates.append(
                VideoSegmentMatch(
                    id=candidate["id"],
                    line_id=line_id,
                    source_video_id=candidate["source_video_id"],
                    index_id=get_settings().tl_index_id,
                    start_time_ms=candidate["start_time_ms"],
                    end_time_ms=candidate["end_time_ms"],
                    score=candidate["score"],
                    generated_by="auto",
                )
            )

    await repo.bulk_insert_lines(lines)
    await repo.attach_candidates(candidates)
    await repo.update_timeline_status(mix_id, "generated")
    logger.info("timeline_worker.completed", mix_id=mix_id, lines=len(lines))


async def health_check(ctx: dict | None) -> None:  # pragma: no cover - cron hook
    logger.info("timeline_worker.health_check")


class WorkerSettings(BaseWorkerSettings):
    functions = [
        "src.workers.timeline_worker.build_timeline",
        "src.workers.timeline_worker.transcribe_lyrics",
        "src.workers.timeline_worker.match_videos",
    ]

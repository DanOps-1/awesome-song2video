"""歌词时间线 Worker。

工作流：
- match_videos: 对已确认的歌词进行视频匹配 (transcribed -> matching -> generated)

注意：歌词获取通过在线服务完成（QQ音乐/网易云/酷狗/LRCLIB），
或用户手动导入。本地 Whisper ASR 已移除。
"""

from __future__ import annotations

import subprocess
import structlog

from pathlib import Path
from uuid import uuid4

from src.domain.models.song_mix import LyricLine, VideoSegmentMatch
from src.infra.config.settings import get_settings
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.pipelines.matching.timeline_builder import TimelineBuilder, TimelineResult
from src.workers import BaseWorkerSettings

logger = structlog.get_logger(__name__)
repo = SongMixRepository()
builder = TimelineBuilder()


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

    await repo.update_timeline_progress(mix_id, 15.0)

    # ====== 进行视频匹配 ======
    async def on_progress(progress: float) -> None:
        # 进度范围: 15% - 90%
        adjusted_progress = 15.0 + progress * 0.75
        await repo.update_timeline_progress(mix_id, adjusted_progress)
        logger.info(
            "timeline_worker.match_progress", mix_id=mix_id, progress=round(adjusted_progress, 1)
        )

    timeline_result: TimelineResult = await builder.match_videos_for_lines(
        lines=lines_for_process,
        audio_duration_ms=audio_duration_ms,
        on_progress=on_progress,
    )

    # ====== 保存结果 ======
    await repo.update_timeline_progress(mix_id, 90.0)

    # 清理旧的歌词行（因为合并后数量可能变化）
    await repo.clear_lyrics(mix_id)

    # 保存合并后的歌词行和视频候选
    new_lines: list[LyricLine] = []
    for index, result_line in enumerate(timeline_result.lines, start=1):
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
    for new_line, result_line in zip(new_lines, timeline_result.lines):
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
                    search_query=candidate.get("search_query"),  # 保存搜索查询文本
                    beat_sync_offset_ms=int(candidate.get("beat_sync_offset_ms", 0)),
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

    # 处理语言（用于未来可能的翻译功能，目前不使用）
    req_language = getattr(mix, "language", "auto")
    target_language = req_language if req_language and req_language != "auto" else None

    # 进度回调：将进度更新到数据库
    async def on_progress(progress: float) -> None:
        await repo.update_timeline_progress(mix_id, progress)
        logger.info("timeline_worker.progress", mix_id=mix_id, progress=round(progress, 1))

    result = await builder.build(
        audio_path=audio_path,
        lyrics_text=mix.lyrics_text,
        language=target_language,
        prompt=None,
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
                    search_query=candidate.get("search_query"),  # 保存搜索查询文本
                    beat_sync_offset_ms=int(candidate.get("beat_sync_offset_ms", 0)),
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
        "src.workers.timeline_worker.match_videos",
    ]

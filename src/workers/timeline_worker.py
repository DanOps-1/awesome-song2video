"""歌词时间线 Worker。"""

from __future__ import annotations

import structlog

from pathlib import Path
from uuid import uuid4

from src.domain.models.song_mix import LyricLine, VideoSegmentMatch
from src.infra.config.settings import get_settings
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.pipelines.matching.timeline_builder import TimelineBuilder
from src.workers import BaseWorkerSettings

logger = structlog.get_logger(__name__)
repo = SongMixRepository()
builder = TimelineBuilder()


async def build_timeline(ctx: dict | None, mix_id: str) -> None:
    logger.info("timeline_worker.started", mix_id=mix_id)
    mix = await repo.get_request(mix_id)
    if mix is None:
        logger.warning("timeline_worker.mix_missing", mix_id=mix_id)
        return
    audio_path = Path(mix.audio_asset_id) if mix.audio_asset_id else None
    
    # 自动构建 Prompt 以避免 Whisper 幻觉
    language = getattr(mix, "language", "zh")
    prompt = None
    if language == "zh":
        prompt = "这是一首中文歌曲的歌词，请忽略背景音乐和非人声部分。"
    elif language == "en":
        prompt = "This is song lyrics, please ignore background music."
        
    result = await builder.build(
        audio_path=audio_path, 
        lyrics_text=mix.lyrics_text,
        language=language,
        prompt=prompt
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
    functions = ["src.workers.timeline_worker.build_timeline"]

"""渲染 Worker：执行 FFmpeg 并输出混剪视频。"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

import structlog

from src.domain.models.metrics import create_render_metrics
from src.domain.models.song_mix import LyricLine, SongMixRequest
from src.infra.config.settings import get_settings
from src.infra.observability.preview_render_metrics import (
    push_render_metrics,
    update_render_queue_depth,
)
from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.pipelines.rendering.ffmpeg_script_builder import FFMpegScriptBuilder, RenderLine
from src.services.matching.twelvelabs_video_fetcher import video_fetcher
from src.workers import BaseWorkerSettings

logger = structlog.get_logger(__name__)
repo = RenderJobRepository()
song_repo = SongMixRepository()
settings = get_settings()
render_semaphore = asyncio.Semaphore(max(1, settings.render_concurrency_limit))


async def render_mix(ctx: dict | None, job_id: str) -> None:
    async with render_semaphore:
        await _render_mix_impl(job_id)


async def _render_mix_impl(job_id: str) -> None:
    """渲染混剪视频的核心实现。

    Args:
        job_id: 渲染任务 ID
    """
    # 获取任务和队列状态
    job = await repo.get(job_id)
    if job is None:
        logger.warning("render_worker.job_missing", job_id=job_id)
        return

    queued_at = job.submitted_at or datetime.utcnow()

    # 记录队列深度
    queue_depth = render_semaphore._value  # 获取当前信号量可用数
    logger.info("render_worker.queue_depth", depth=queue_depth, job_id=job_id)
    update_render_queue_depth(settings.render_concurrency_limit - queue_depth)

    mix = await song_repo.get_request(job.mix_request_id)
    if mix is None:
        logger.error("render_worker.mix_missing", job_id=job_id, mix_id=job.mix_request_id)
        await repo.mark_failure(job_id, error_log="mix not found")
        return

    lines = await song_repo.list_locked_lines(job.mix_request_id)
    if not lines:
        logger.warning("render_worker.no_lines", job_id=job_id, mix_id=job.mix_request_id)
        await repo.mark_failure(job_id, error_log="no locked lines")
        return

    # 开始渲染
    await repo.update_status(job_id, status="running")
    logger.info("render_worker.started", job_id=job_id, mix_id=job.mix_request_id)

    try:
        render_lines = [_build_render_line(line) for line in lines]
        builder = FFMpegScriptBuilder(resolution="1080p", frame_rate=25)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            builder.write_edl(render_lines, tmp_path / "timeline.json")
            clips = _extract_clips(render_lines, tmp_path)
            concat_file = tmp_path / "concat.txt"
            concat_file.write_text("".join([f"file '{clip.as_posix()}'\n" for clip in clips]))
            output_video = tmp_path / f"{job_id}.mp4"
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    concat_file.as_posix(),
                    "-c",
                    "copy",
                    output_video.as_posix(),
                ]
            )
            audio_path = _resolve_audio_path(mix)
            if audio_path:
                audio_enriched = tmp_path / f"{job_id}_with_audio.mp4"
                _attach_audio_track(output_video, audio_path, audio_enriched)
                output_video = audio_enriched
            subtitle_file = _write_srt(render_lines, tmp_path / f"{job_id}.srt")

            # 计算对齐指标
            finished_at = datetime.utcnow()
            alignment_data = _calculate_alignment(render_lines)

            # 创建完整的 render metrics
            render_metrics_dict = create_render_metrics(
                line_count=int(alignment_data["line_count"]),
                avg_delta_ms=float(alignment_data["avg_delta_ms"]),
                max_delta_ms=float(alignment_data["max_delta_ms"]),
                total_duration_ms=int(alignment_data["total_duration_ms"]),
                queued_at=queued_at,
                finished_at=finished_at,
            )

            # 将视频文件和字幕文件复制到持久化目录
            output_dir = Path("artifacts/renders")
            output_dir.mkdir(parents=True, exist_ok=True)
            final_output = output_dir / f"{job_id}.mp4"
            final_subtitle = output_dir / f"{job_id}.srt"
            shutil.copy2(output_video, final_output)
            shutil.copy2(subtitle_file, final_subtitle)

            output_object = final_output.as_posix()

            # 检查 MinIO 是否可用
            if not settings.minio_endpoint:
                logger.warning(
                    "render_worker.storage_todo",
                    message="MinIO 未启用，产物仅存本地",
                    local_path=output_object,
                    subtitle_path=final_subtitle.as_posix(),
                    job_id=job_id,
                )
            else:
                logger.info(
                    "render_worker.storage_todo",
                    message="TODO: 实现 MinIO 上传",
                    local_path=output_object,
                    subtitle_path=final_subtitle.as_posix(),
                    job_id=job_id,
                )

        # 保存成功结果和 metrics
        await repo.mark_success(
            job_id, output_asset_id=output_object, metrics={"render": render_metrics_dict}
        )

        # 推送 OTEL 指标
        push_render_metrics(
            job_id=job_id,
            mix_id=job.mix_request_id,
            line_count=render_metrics_dict["line_count"],
            avg_delta_ms=render_metrics_dict["avg_delta_ms"],
            max_delta_ms=render_metrics_dict["max_delta_ms"],
            total_duration_ms=render_metrics_dict["total_duration_ms"],
            owner_id=mix.owner_id if mix else None,
        )

        logger.info(
            "render_worker.completed",
            job_id=job_id,
            mix_id=job.mix_request_id,
            line_count=render_metrics_dict["line_count"],
            avg_delta_ms=render_metrics_dict["avg_delta_ms"],
            max_delta_ms=render_metrics_dict["max_delta_ms"],
        )

    except Exception as exc:
        logger.error("render_worker.failed", job_id=job_id, error=str(exc), exc_info=True)
        await repo.mark_failure(job_id, error_log=str(exc))
        raise


def _build_render_line(line: LyricLine) -> RenderLine:
    candidates = getattr(line, "candidates", []) or []
    if line.selected_segment_id and candidates:
        selected = next((c for c in candidates if c.id == line.selected_segment_id), None)
    else:
        selected = candidates[0] if candidates else None
    source_video_id = selected.source_video_id if selected else settings.fallback_video_id
    start_ms = selected.start_time_ms if selected else line.start_time_ms
    end_ms = selected.end_time_ms if selected else line.end_time_ms
    return RenderLine(
        source_video_id=source_video_id,
        start_time_ms=start_ms,
        end_time_ms=end_ms,
        lyrics=line.original_text,
        lyric_start_ms=line.start_time_ms,
        lyric_end_ms=line.end_time_ms,
    )


def _extract_clips(lines: Iterable[RenderLine], tmp_path: Path) -> list[Path]:
    clips: list[Path] = []
    for idx, line in enumerate(lines):
        clip_path = tmp_path / f"clip_{idx}.mp4"
        clip = video_fetcher.fetch_clip(line.source_video_id, line.start_time_ms, line.end_time_ms, clip_path)
        if clip is None or not clip.exists():
            logger.warning("render_worker.clip_failed", video_id=line.source_video_id, idx=idx)
            continue
        clips.append(clip)
    return clips


def _write_srt(lines: Iterable[RenderLine], path: Path) -> Path:
    rows = []
    for idx, line in enumerate(lines, start=1):
        start = _format_timestamp(line.lyric_start_ms)
        end = _format_timestamp(line.lyric_end_ms)
        rows.append(f"{idx}\n{start} --> {end}\n{line.lyrics}\n\n")
    path.write_text("".join(rows), encoding="utf-8")
    return path


def _format_timestamp(ms: int) -> str:
    seconds, milli = divmod(ms, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{sec:02d},{milli:03d}"


def _run_ffmpeg(cmd: list[str]) -> None:
    try:
        logger.info("render_worker.ffmpeg", cmd=" ".join(cmd))
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        logger.error("ffmpeg.not_found", cmd=cmd)
    except subprocess.CalledProcessError as exc:  # noqa: BLE001
        logger.error("ffmpeg.failed", returncode=exc.returncode, cmd=cmd)


def _calculate_alignment(lines: Iterable[RenderLine]) -> dict[str, float]:
    deltas: list[int] = []
    total_duration = 0
    count = 0
    for line in lines:
        lyric_duration = max(0, line.lyric_end_ms - line.lyric_start_ms)
        clip_duration = max(0, line.end_time_ms - line.start_time_ms)
        deltas.append(abs(lyric_duration - clip_duration))
        total_duration += lyric_duration
        count += 1
    return {
        "line_count": count,
        "avg_delta_ms": sum(deltas) / len(deltas) if deltas else 0,
        "max_delta_ms": max(deltas) if deltas else 0,
        "total_duration_ms": total_duration,
    }


def _resolve_audio_path(mix: SongMixRequest | None) -> Path | None:
    if mix is None or not mix.audio_asset_id:
        return None
    candidate = Path(mix.audio_asset_id)
    if candidate.exists():
        return candidate
    fallback = Path(settings.audio_asset_dir) / mix.audio_asset_id
    if fallback.exists():
        return fallback
    logger.warning("render_worker.audio_missing", path=mix.audio_asset_id)
    return None


def _attach_audio_track(video_path: Path, audio_path: Path, target_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path.as_posix(),
        "-i",
        audio_path.as_posix(),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-shortest",
        target_path.as_posix(),
    ]
    _run_ffmpeg(cmd)


class WorkerSettings(BaseWorkerSettings):
    functions = ["src.workers.render_worker.render_mix"]

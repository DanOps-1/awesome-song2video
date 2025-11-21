"""渲染 Worker：执行 FFmpeg 并输出混剪视频。"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

import structlog

from src.domain.models.metrics import create_render_metrics
from src.domain.models.render_clip_config import RenderClipConfig
from src.domain.models.song_mix import LyricLine, SongMixRequest
from src.domain.services.render_clip_scheduler import ClipDownloadResult, ClipDownloadTask, RenderClipScheduler
from src.domain.services.render_reporter import build_clip_stats
from src.infra.config.settings import get_settings
from src.infra.messaging.render_config_watcher import RenderConfigWatcher
from src.infra.observability.preview_render_metrics import (
    add_clip_failure,
    observe_clip_duration,
    push_render_metrics,
    set_clip_inflight,
    update_render_queue_depth,
)
from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.pipelines.rendering.ffmpeg_script_builder import FFMpegScriptBuilder, RenderLine
from src.services.matching.twelvelabs_video_fetcher import video_fetcher
from src.services.render.placeholder_manager import cleanup_tmp_root, ensure_tmp_root
from src.workers import BaseWorkerSettings

logger = structlog.get_logger(__name__)
repo = RenderJobRepository()
song_repo = SongMixRepository()
settings = get_settings()
render_semaphore = asyncio.Semaphore(max(1, settings.render_concurrency_limit))
clip_config = RenderClipConfig.from_settings(settings)
_config_watcher: RenderConfigWatcher | None = None


async def render_mix(ctx: dict | None, job_id: str) -> None:
    async with render_semaphore:
        await _render_mix_impl(job_id)


async def on_startup(ctx: dict) -> dict:
    global _config_watcher

    async def _handle_update(new_config: RenderClipConfig) -> None:
        global clip_config
        clip_config = new_config
        logger.info("render_worker.config_hot_reload", config=new_config.model_dump())

    _config_watcher = RenderConfigWatcher(_handle_update)
    await _config_watcher.start()
    ctx["clip_config"] = clip_config
    return ctx


async def on_shutdown(ctx: dict) -> None:
    global _config_watcher
    if _config_watcher:
        await _config_watcher.stop()
        _config_watcher = None


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

        tmp_root = ensure_tmp_root()
        with tempfile.TemporaryDirectory(dir=tmp_root.as_posix()) as tmp_dir:
            tmp_path = Path(tmp_dir)
            builder.write_edl(render_lines, tmp_path / "timeline.json")
            clips, clip_stats = await _extract_clips(render_lines, job_id, tmp_path)
            concat_file = tmp_path / "concat.txt"
            # 使用文件名而非绝对路径（所有 clip 都在同一目录下）
            concat_file.write_text("".join([f"file '{clip.name}'\n" for clip in clips]))
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
            render_metrics_dict["clip_stats"] = clip_stats

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
    finally:
        cleanup_tmp_root()


def _build_render_line(line: LyricLine) -> RenderLine:
    from src.pipelines.rendering.ffmpeg_script_builder import VideoCandidate

    candidates = getattr(line, "candidates", []) or []
    if line.selected_segment_id and candidates:
        selected = next((c for c in candidates if c.id == line.selected_segment_id), None)
    else:
        selected = candidates[0] if candidates else None
    source_video_id = selected.source_video_id if selected else settings.fallback_video_id
    start_ms = selected.start_time_ms if selected else line.start_time_ms
    end_ms = selected.end_time_ms if selected else line.end_time_ms

    # 转换所有候选片段为 VideoCandidate
    video_candidates = [
        VideoCandidate(
            video_id=c.source_video_id,
            start_ms=c.start_time_ms,
            end_ms=c.end_time_ms,
            score=getattr(c, "score", 0.0),
        )
        for c in candidates
    ] if candidates else None

    return RenderLine(
        source_video_id=source_video_id,
        start_time_ms=start_ms,
        end_time_ms=end_ms,
        lyrics=line.original_text,
        lyric_start_ms=line.start_time_ms,
        lyric_end_ms=line.end_time_ms,
        candidates=video_candidates,
    )


async def _extract_clips(lines: list[RenderLine], job_id: str, tmp_path: Path) -> tuple[list[Path], dict[str, float | int | str]]:
    scheduler = RenderClipScheduler(
        max_parallelism=clip_config.max_parallelism,
        per_video_limit=clip_config.per_video_limit,
        max_retry=clip_config.max_retry,
        retry_backoff_base_ms=clip_config.retry_backoff_base_ms,
    )
    clip_tasks = [
        ClipDownloadTask(
            idx=idx,
            video_id=line.source_video_id,
            start_ms=line.start_time_ms,
            end_ms=line.end_time_ms,
            target_path=tmp_path / f"clip_{idx}.mp4",
        )
        for idx, line in enumerate(lines)
    ]

    inflight = 0
    peak_parallelism = 0
    inflight_lock = asyncio.Lock()
    duration_lock = asyncio.Lock()
    durations: list[float] = []

    async def _worker(task: ClipDownloadTask) -> ClipDownloadResult:
        nonlocal inflight, peak_parallelism
        line = lines[task.idx]
        async with inflight_lock:
            inflight += 1
            peak_parallelism = max(peak_parallelism, inflight)
            parallel_slot = inflight - 1
            set_clip_inflight(inflight, job_id=job_id, video_id=task.video_id)
        logger.info(
            "render_worker.clip_task_start",
            clip_task_id=task.clip_task_id,
            job_id=job_id,
            video_id=task.video_id,
            parallel_slot=parallel_slot,
            total_candidates=len(line.candidates) if line.candidates else 1,
        )
        start = time.perf_counter()

        # 获取候选列表（如果有的话）
        candidates_to_try = line.candidates if line.candidates else None
        last_error: Exception | None = None

        # 如果有多个候选，依次尝试
        if candidates_to_try and len(candidates_to_try) > 1:
            for idx, candidate in enumerate(candidates_to_try):
                try:
                    logger.info(
                        "render_worker.try_candidate",
                        clip_task_id=task.clip_task_id,
                        job_id=job_id,
                        candidate_idx=idx,
                        total_candidates=len(candidates_to_try),
                        video_id=candidate.video_id,
                        score=candidate.score,
                    )
                    clip_path = await asyncio.to_thread(
                        video_fetcher.fetch_clip,
                        candidate.video_id,
                        candidate.start_ms,
                        candidate.end_ms,
                        task.target_path,
                    )
                    if clip_path and clip_path.exists():
                        # 成功！
                        duration_ms = (time.perf_counter() - start) * 1000
                        observe_clip_duration(duration_ms, job_id=job_id, video_id=candidate.video_id)
                        async with duration_lock:
                            durations.append(duration_ms)
                        logger.info(
                            "render_worker.clip_task_end",
                            clip_task_id=task.clip_task_id,
                            job_id=job_id,
                            video_id=candidate.video_id,
                            candidate_idx=idx,
                            status="success",
                            duration_ms=round(duration_ms, 2),
                            parallel_slot=parallel_slot,
                        )
                        return ClipDownloadResult(task=task, status="success", path=clip_path, duration_ms=duration_ms)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    logger.warning(
                        "render_worker.candidate_failed",
                        clip_task_id=task.clip_task_id,
                        job_id=job_id,
                        candidate_idx=idx,
                        video_id=candidate.video_id,
                        error=str(exc),
                        will_retry=idx < len(candidates_to_try) - 1,
                    )
                    # 继续尝试下一个候选
                    continue

            # 所有候选都失败了
            add_clip_failure(job_id=job_id, video_id=task.video_id, reason="all_candidates_failed")
            logger.error(
                "render_worker.all_candidates_failed",
                clip_task_id=task.clip_task_id,
                job_id=job_id,
                total_tried=len(candidates_to_try),
            )
            raise RuntimeError(f"All {len(candidates_to_try)} candidates failed") from last_error

        # 没有多个候选，使用原有逻辑
        try:
            clip_path = await asyncio.to_thread(
                video_fetcher.fetch_clip,
                line.source_video_id,
                line.start_time_ms,
                line.end_time_ms,
                task.target_path,
            )
            if clip_path is None or not clip_path.exists():
                raise RuntimeError("clip_not_generated")
            duration_ms = (time.perf_counter() - start) * 1000
            observe_clip_duration(duration_ms, job_id=job_id, video_id=task.video_id)
            async with duration_lock:
                durations.append(duration_ms)
            logger.info(
                "render_worker.clip_task_end",
                clip_task_id=task.clip_task_id,
                job_id=job_id,
                video_id=task.video_id,
                status="success",
                duration_ms=round(duration_ms, 2),
                parallel_slot=parallel_slot,
            )
            return ClipDownloadResult(task=task, status="success", path=clip_path, duration_ms=duration_ms)
        except Exception as exc:  # noqa: BLE001
            add_clip_failure(job_id=job_id, video_id=task.video_id, reason=type(exc).__name__)
            logger.warning(
                "render_worker.clip_task_failed",
                clip_task_id=task.clip_task_id,
                job_id=job_id,
                video_id=task.video_id,
                error=str(exc),
                parallel_slot=parallel_slot,
            )
            raise
        finally:
            async with inflight_lock:
                inflight -= 1
                set_clip_inflight(inflight, job_id=job_id, video_id=task.video_id)

    results = await scheduler.run(clip_tasks, _worker)
    results.sort(key=lambda r: r.task.idx)

    clips: list[Path] = []
    failed = 0
    failed_clips: list[tuple[int, str]] = []  # (idx, video_id)

    for result in results:
        if result.status == "success" and result.path:
            clips.append(result.path)
        else:
            failed += 1
            failed_clips.append((result.task.idx, result.task.video_id))
            logger.error(
                "render_worker.clip_download_failed",
                clip_task_id=result.task.clip_task_id,
                job_id=job_id,
                video_id=result.task.video_id,
                idx=result.task.idx,
            )

    # 如果有任何片段下载失败，抛出异常而不是用占位符掩盖
    if failed > 0:
        error_msg = f"Failed to download {failed}/{len(clip_tasks)} clips: {failed_clips[:5]}"
        logger.error(
            "render_worker.extract_clips_failed",
            job_id=job_id,
            failed=failed,
            total=len(clip_tasks),
            failed_clips=failed_clips,
        )
        raise RuntimeError(error_msg)

    clip_stats = build_clip_stats(
        total=len(clip_tasks),
        success=len(clips),
        failed=0,  # 如果走到这里，说明没有失败
        placeholder=0,
        durations=durations,
        peak_parallelism=peak_parallelism,
    )
    return clips, clip_stats


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
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        logger.error("ffmpeg.not_found", cmd=cmd, error=str(exc))
        raise RuntimeError(f"FFmpeg not found. Please install ffmpeg: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        stderr_output = exc.stderr if exc.stderr else "No error output"
        logger.error(
            "ffmpeg.failed",
            returncode=exc.returncode,
            cmd=cmd,
            stderr=stderr_output[:500],  # 只记录前500字符
        )
        raise RuntimeError(
            f"FFmpeg command failed with return code {exc.returncode}.\n"
            f"Command: {' '.join(cmd)}\n"
            f"Error: {stderr_output}"
        ) from exc


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
    # 🔧 修复视频时长被截断问题
    # 问题：使用 -shortest 会以最短流为准，如果视频片段总时长不足，会截断音频
    # 解决：使用 tpad 滤镜延长视频（冻结最后一帧），确保视频时长 >= 音频时长

    # 先获取音频和视频时长
    import subprocess

    def get_duration(path: Path) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path.as_posix()],
            capture_output=True, text=True, check=False
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0

    video_duration = get_duration(video_path)
    audio_duration = get_duration(audio_path)

    logger.info(
        "render_worker.attach_audio",
        video_duration=video_duration,
        audio_duration=audio_duration,
        diff=audio_duration - video_duration,
    )

    if audio_duration > video_duration + 0.5:  # 音频比视频长超过0.5秒
        # 使用 tpad 滤镜延长视频（冻结最后一帧）
        pad_duration = audio_duration - video_duration
        logger.warning(
            "render_worker.video_too_short",
            video_duration=video_duration,
            audio_duration=audio_duration,
            pad_duration=pad_duration,
            message="视频比音频短，将冻结最后一帧补齐",
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path.as_posix(),
            "-i", audio_path.as_posix(),
            "-filter_complex",
            f"[0:v]tpad=stop_mode=clone:stop_duration={pad_duration}[v]",
            "-map", "[v]",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            target_path.as_posix(),
        ]
    else:
        # 视频时长足够，直接复制
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path.as_posix(),
            "-i", audio_path.as_posix(),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",  # 视频够长时使用 -shortest
            target_path.as_posix(),
        ]

    _run_ffmpeg(cmd)


class WorkerSettings(BaseWorkerSettings):
    functions = ["src.workers.render_worker.render_mix"]
    on_startup = "src.workers.render_worker.on_startup"
    on_shutdown = "src.workers.render_worker.on_shutdown"

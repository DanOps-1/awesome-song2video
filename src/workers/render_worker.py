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
from src.domain.services.render_clip_scheduler import (
    ClipDownloadResult,
    ClipDownloadTask,
    RenderClipScheduler,
)
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

# 宽高比到分辨率的映射（短视频常用比例）
ASPECT_RATIO_MAP: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),  # 横屏 - YouTube/B站
    "9:16": (1080, 1920),  # 竖屏 - 抖音/TikTok/快手/小红书
    "1:1": (1080, 1080),   # 正方形 - Instagram/微信
    "4:3": (1440, 1080),   # 传统比例
}
DEFAULT_ASPECT_RATIO = "16:9"


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
        await song_repo.update_status(job.mix_request_id, render_status="failed")
        return

    lines = await song_repo.list_locked_lines(job.mix_request_id)
    if not lines:
        logger.warning("render_worker.no_lines", job_id=job_id, mix_id=job.mix_request_id)
        await repo.mark_failure(job_id, error_log="no locked lines")
        await song_repo.update_status(job.mix_request_id, render_status="failed")
        return

    # 开始渲染
    await repo.update_status(job_id, status="running")
    await repo.update_progress(job_id, 0.0)
    await song_repo.update_status(job.mix_request_id, render_status="running")
    logger.info("render_worker.started", job_id=job_id, mix_id=job.mix_request_id)

    try:
        render_lines = [_build_render_line(line) for line in lines]
        builder = FFMpegScriptBuilder(resolution="1080p", frame_rate=25)

        tmp_root = ensure_tmp_root()
        with tempfile.TemporaryDirectory(dir=tmp_root.as_posix()) as tmp_dir:
            tmp_path = Path(tmp_dir)
            builder.write_edl(render_lines, tmp_path / "timeline.json")
            await repo.update_progress(job_id, 5.0)  # 5%: 准备完成
            clips, clip_stats = await _extract_clips(render_lines, job_id, tmp_path)
            await repo.update_progress(job_id, 50.0)  # 50%: 片段下载完成
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
                    "-map",
                    "0:v",  # 只选择视频流，移除原视频音频
                    "-c:v",
                    "copy",
                    output_video.as_posix(),
                ]
            )
            await repo.update_progress(job_id, 70.0)  # 70%: 视频合并完成
            audio_path = _resolve_audio_path(mix)
            if audio_path:
                audio_enriched = tmp_path / f"{job_id}_with_audio.mp4"
                _attach_audio_track(output_video, audio_path, audio_enriched, render_lines)
                output_video = audio_enriched

            await repo.update_progress(job_id, 85.0)  # 85%: 音频添加完成
            # 生成字幕文件并烧录到视频
            subtitle_file = _write_srt(render_lines, tmp_path / f"{job_id}.srt")
            video_with_subtitles = tmp_path / f"{job_id}_with_subtitles.mp4"
            # 根据用户选择的宽高比确定输出分辨率
            aspect_ratio = getattr(mix, "aspect_ratio", DEFAULT_ASPECT_RATIO)
            target_width, target_height = ASPECT_RATIO_MAP.get(
                aspect_ratio, ASPECT_RATIO_MAP[DEFAULT_ASPECT_RATIO]
            )
            logger.info(
                "render_worker.output_resolution",
                job_id=job_id,
                aspect_ratio=aspect_ratio,
                resolution=f"{target_width}x{target_height}",
            )
            _burn_subtitles(
                output_video,
                subtitle_file,
                video_with_subtitles,
                target_width=target_width,
                target_height=target_height,
            )
            output_video = video_with_subtitles
            await repo.update_progress(job_id, 95.0)  # 95%: 字幕烧录完成

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
        await repo.update_progress(job_id, 100.0)  # 100%: 完成
        await repo.mark_success(
            job_id, output_asset_id=output_object, metrics={"render": render_metrics_dict}
        )
        await song_repo.update_status(job.mix_request_id, render_status="success")

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
        await song_repo.update_status(job.mix_request_id, render_status="failed")
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
    video_candidates = (
        [
            VideoCandidate(
                video_id=c.source_video_id,
                start_ms=c.start_time_ms,
                end_ms=c.end_time_ms,
                score=getattr(c, "score", 0.0),
            )
            for c in candidates
        ]
        if candidates
        else None
    )

    return RenderLine(
        source_video_id=source_video_id,
        start_time_ms=start_ms,
        end_time_ms=end_ms,
        lyrics=line.original_text,
        lyric_start_ms=line.start_time_ms,
        lyric_end_ms=line.end_time_ms,
        candidates=video_candidates,
    )


async def _extract_clips(
    lines: list[RenderLine], job_id: str, tmp_path: Path
) -> tuple[list[Path], dict[str, float | int | str]]:
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
    completed_count = 0
    total_clips = len(clip_tasks)
    inflight_lock = asyncio.Lock()
    duration_lock = asyncio.Lock()
    progress_lock = asyncio.Lock()
    durations: list[float] = []

    async def update_clip_progress() -> None:
        """更新片段下载进度: 5% - 50%"""
        nonlocal completed_count
        async with progress_lock:
            completed_count += 1
            # 进度范围: 5% 到 50%，共 45%
            progress = 5.0 + (completed_count / total_clips) * 45.0
            await repo.update_progress(job_id, progress)

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
                        observe_clip_duration(
                            duration_ms, job_id=job_id, video_id=candidate.video_id
                        )
                        async with duration_lock:
                            durations.append(duration_ms)
                        await update_clip_progress()  # 更新下载进度
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
                        return ClipDownloadResult(
                            task=task, status="success", path=clip_path, duration_ms=duration_ms
                        )
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
            await update_clip_progress()  # 更新下载进度
            logger.info(
                "render_worker.clip_task_end",
                clip_task_id=task.clip_task_id,
                job_id=job_id,
                video_id=task.video_id,
                status="success",
                duration_ms=round(duration_ms, 2),
                parallel_slot=parallel_slot,
            )
            return ClipDownloadResult(
                task=task, status="success", path=clip_path, duration_ms=duration_ms
            )
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
    """生成 SRT 字幕文件，时间戳相对于第一个歌词开始时间（从0开始）。

    因为音频会被裁剪到只包含歌词部分，所以字幕时间也需要相应调整。
    """
    rows = []
    lines_list = list(lines)
    if not lines_list:
        path.write_text("", encoding="utf-8")
        return path

    # 获取第一个歌词的开始时间作为基准
    offset_ms = lines_list[0].lyric_start_ms

    for idx, line in enumerate(lines_list, start=1):
        # 减去偏移量，让字幕从 0 开始
        start = _format_timestamp(line.lyric_start_ms - offset_ms)
        end = _format_timestamp(line.lyric_end_ms - offset_ms)
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

    # 先尝试直接路径
    candidate = Path(mix.audio_asset_id)
    if candidate.exists():
        return candidate

    # 尝试在音频目录下查找
    audio_dir = Path(settings.audio_asset_dir)

    # 如果 audio_asset_id 是完整文件名（带扩展名）
    fallback = audio_dir / mix.audio_asset_id
    if fallback.exists():
        return fallback

    # 如果 audio_asset_id 是文件名的 stem（不带扩展名），尝试各种扩展名
    for ext in (".mp3", ".wav", ".flac", ".m4a", ".aac"):
        fallback = audio_dir / f"{mix.audio_asset_id}{ext}"
        if fallback.exists():
            logger.info("render_worker.audio_resolved", path=str(fallback))
            return fallback

    # 在音频目录下搜索匹配的文件
    for path in audio_dir.rglob("*"):
        if path.is_file() and path.stem == mix.audio_asset_id:
            logger.info("render_worker.audio_found_by_stem", path=str(path))
            return path

    logger.warning(
        "render_worker.audio_missing", audio_asset_id=mix.audio_asset_id, audio_dir=str(audio_dir)
    )
    return None


def _attach_audio_track(
    video_path: Path, audio_path: Path, target_path: Path, render_lines: list[RenderLine]
) -> None:
    """将音频轨道附加到视频上，并裁剪音频以匹配歌词时间轴。

    关键修复：
    - 视频片段对应的是歌词的时间范围（例如从 0.779s 开始）
    - 原始音频是完整的（从 0s 开始）
    - 需要裁剪音频，只保留歌词对应的时间段，这样音频和视频的时间轴才能对齐

    Args:
        video_path: 拼接好的视频文件路径
        audio_path: 原始音频文件路径
        target_path: 输出文件路径
        render_lines: 渲染行列表，包含歌词时间信息
    """
    import subprocess

    def get_duration(path: Path) -> float:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path.as_posix(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0

    # 获取歌词的起止时间
    if not render_lines:
        logger.warning("render_worker.no_render_lines", message="没有渲染行，无法裁剪音频")
        # 回退到不裁剪的方式
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
        return

    first_lyric_start_ms = render_lines[0].lyric_start_ms
    last_lyric_end_ms = render_lines[-1].lyric_end_ms

    # 转换为秒
    start_sec = first_lyric_start_ms / 1000.0
    duration_sec = (last_lyric_end_ms - first_lyric_start_ms) / 1000.0

    video_duration = get_duration(video_path)
    audio_duration = get_duration(audio_path)

    logger.info(
        "render_worker.attach_audio_with_trim",
        video_duration=round(video_duration, 2),
        audio_duration=round(audio_duration, 2),
        audio_trim_start=round(start_sec, 3),
        audio_trim_duration=round(duration_sec, 3),
        first_lyric_start_ms=first_lyric_start_ms,
        last_lyric_end_ms=last_lyric_end_ms,
    )

    # 裁剪音频并合并
    # -ss: 起始时间
    # -t: 持续时间
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path.as_posix(),
        "-ss",
        str(start_sec),  # 从歌词开始位置裁剪音频
        "-t",
        str(duration_sec),  # 裁剪时长
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
        "-shortest",  # 以较短的流为准
        target_path.as_posix(),
    ]

    _run_ffmpeg(cmd)


def _burn_subtitles(
    video_path: Path,
    subtitle_path: Path,
    target_path: Path,
    target_width: int = 1920,
    target_height: int = 1080,
) -> None:
    """将字幕烧录到视频中，并统一缩放到目标分辨率(16:9)。

    Args:
        video_path: 输入视频文件路径
        subtitle_path: SRT 字幕文件路径
        target_path: 输出视频文件路径
        target_width: 目标宽度（默认 1920）
        target_height: 目标高度（默认 1080）

    使用 FFmpeg 滤镜链：
    1. scale: 缩放到目标分辨率，保持原始宽高比
    2. pad: 添加黑边居中（letterbox/pillarbox）
    3. subtitles: 烧录字幕

    字幕样式：
    - 字体：Arial (兼容性好)
    - 大小：24
    - 主颜色：白色
    - 边框颜色：黑色
    - 位置：底部居中
    """
    logger.info(
        "render_worker.burn_subtitles",
        video=video_path.as_posix(),
        subtitle=subtitle_path.as_posix(),
        target=target_path.as_posix(),
        target_resolution=f"{target_width}x{target_height}",
    )

    # 注意：Windows 路径需要转义反斜杠
    subtitle_path_str = subtitle_path.as_posix().replace("\\", "/").replace(":", "\\:")

    # 构建视频滤镜链：
    # 1. scale: 保持宽高比缩放到目标尺寸内
    # 2. pad: 添加黑边使其达到目标尺寸（居中）
    # 3. subtitles: 烧录字幕
    scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease"
    pad_filter = f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
    subtitle_filter = f"subtitles={subtitle_path_str}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,MarginV=50'"

    # 组合滤镜链
    vf_chain = f"{scale_filter},{pad_filter},{subtitle_filter}"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path.as_posix(),
        "-vf",
        vf_chain,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "copy",
        target_path.as_posix(),
    ]

    _run_ffmpeg(cmd)

    logger.info(
        "render_worker.subtitles_burned",
        output_size=target_path.stat().st_size if target_path.exists() else 0,
        message="字幕已烧录到视频",
    )


class WorkerSettings(BaseWorkerSettings):
    functions = ["src.workers.render_worker.render_mix"]
    on_startup = on_startup
    on_shutdown = on_shutdown

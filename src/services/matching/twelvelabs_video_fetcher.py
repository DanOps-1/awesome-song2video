"""TwelveLabs 视频素材下载工具。

支持直接从 HLS 流按时间窗拉取片段，避免全量下载。
"""

from __future__ import annotations

import random
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.infra.config.settings import AppSettings, get_settings

logger = structlog.get_logger(__name__)


class TwelveLabsVideoFetcher:
    """基于 retrieve API 下载视频片段，不落本地全量文件。"""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._live_enabled = bool(self._settings.tl_live_enabled)
        self._base_urls = self._build_base_url_chain()
        self._stream_cache: dict[str, str] = {}
        self._locks_lock = threading.Lock()
        self._per_video_locks: dict[str, threading.Semaphore] = {}

    def fetch_clip(self, video_id: str, start_ms: int, end_ms: int, target: Path) -> Path | None:
        """按时间窗拉取视频片段到目标路径（仅临时使用，不保留全量文件）。

        使用精确裁剪模式（output seeking + reencode），确保：
        1. 每个片段时长与指定时长完全一致（毫秒级精度）
        2. 多个片段拼接后总时长与音频完全对齐
        3. 字幕时间戳与画面完美同步
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        start_ms = max(0, start_ms)
        end_ms = max(end_ms, start_ms + 500)

        # 优先实时拉取 HLS 片段（使用精确裁剪）
        if self._live_enabled:
            lock = self._get_video_lock(video_id)
            acquired = lock.acquire(blocking=False)
            if not acquired:
                logger.info(
                    "twelvelabs.per_video_limit_wait",
                    video_id=video_id,
                    limit=self._settings.render_per_video_limit,
                )
                lock.acquire()
            try:
                stream_url = self._get_stream_url(video_id)
                if stream_url:
                    # 使用精确裁剪模式（重新编码）
                    if self._cut_clip(stream_url, start_ms, end_ms, target, video_id):
                        return target
            finally:
                lock.release()

        # 回退：若本地已有手动放置的全量文件，则从本地截取
        local_source = Path(self._settings.video_asset_dir) / f"{video_id}.mp4"
        if local_source.exists():
            if self._cut_clip(local_source.as_posix(), start_ms, end_ms, target, video_id, is_local=True):
                return target

        logger.warning("twelvelabs.clip_unavailable", video_id=video_id, start_ms=start_ms, end_ms=end_ms)
        return None

    def _retrieve_video_payload(self, video_id: str) -> dict[str, Any] | None:
        headers = {"x-api-key": self._settings.tl_api_key}
        for base in self._base_urls:
            url = self._build_retrieve_url(base, video_id)
            try:
                time.sleep(random.uniform(0, 0.5))
                response = httpx.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
                logger.info("twelvelabs.retrieve_success", video_id=video_id, base_url=base or "default")
                payload: dict[str, Any] = response.json()
                return payload
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "twelvelabs.retrieve_http_error",
                    video_id=video_id,
                    base_url=base or "default",
                    status=exc.response.status_code,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "twelvelabs.retrieve_exception",
                    video_id=video_id,
                    base_url=base or "default",
                    error=str(exc),
                )
        return None

    def _get_stream_url(self, video_id: str) -> str | None:
        if video_id in self._stream_cache:
            return self._stream_cache[video_id]
        payload = self._retrieve_video_payload(video_id)
        if payload is None:
            logger.warning("twelvelabs.retrieve_failed_all", video_id=video_id)
            return None
        stream_url = self._extract_stream_url(payload)
        if not stream_url:
            logger.error("twelvelabs.video_url_missing", video_id=video_id)
            return None
        self._stream_cache[video_id] = stream_url
        return stream_url

    def _extract_stream_url(self, payload: dict[str, Any]) -> str | None:
        hls = payload.get("hls") or {}
        video_url = hls.get("video_url")
        if video_url:
            return str(video_url)
        fallback_url = payload.get("video_url")
        return str(fallback_url) if fallback_url else None

    def _build_base_url_chain(self) -> list[str | None]:
        urls: list[str | None] = []
        custom = self._settings.tl_api_base_url
        if custom:
            urls.append(custom.rstrip("/"))
        urls.append(None)  # 默认 https://api.twelvelabs.io
        urls.append("https://api.twelvelabs.com/v1.3")
        seen: set[str | None] = set()
        unique: list[str | None] = []
        for url in urls:
            if url not in seen:
                unique.append(url)
                seen.add(url)
        return unique

    def _build_retrieve_url(self, base: str | None, video_id: str) -> str:
        prefix = base or "https://api.twelvelabs.io"
        prefix = prefix.rstrip("/")
        if not prefix.endswith("/v1.3"):
            prefix = f"{prefix}/v1.3"
        return f"{prefix}/indexes/{self._settings.tl_index_id}/videos/{video_id}"

    def _cut_clip(
        self,
        source_url: str,
        start_ms: int,
        end_ms: int,
        target: Path,
        video_id: str,
        *,
        is_local: bool = False,
    ) -> bool:
        duration = max((end_ms - start_ms) / 1000.0, 0.5)

        # 🛡️ 边界检查：获取源视频时长，防止裁剪范围超出
        source_duration_ms = self._get_video_duration_ms(source_url)
        if source_duration_ms and start_ms >= source_duration_ms:
            logger.warning(
                "twelvelabs.clip_out_of_bounds",
                video_id=video_id,
                start_ms=start_ms,
                end_ms=end_ms,
                source_duration_ms=source_duration_ms,
                message="裁剪起始时间超出视频时长，尝试循环裁剪",
            )
            # 使用循环输入（-stream_loop）从头开始裁剪所需时长
            return self._cut_clip_with_loop(source_url, duration, target, video_id)

        # 如果裁剪结束时间超出，调整到视频末尾
        if source_duration_ms and end_ms > source_duration_ms:
            original_end = end_ms
            # 调整裁剪范围到视频末尾
            end_ms = int(source_duration_ms)
            start_ms = max(0, end_ms - int(duration * 1000))
            duration = (end_ms - start_ms) / 1000.0
            logger.warning(
                "twelvelabs.clip_adjusted",
                video_id=video_id,
                original_start_ms=start_ms,
                original_end_ms=original_end,
                adjusted_start_ms=start_ms,
                adjusted_end_ms=end_ms,
                source_duration_ms=source_duration_ms,
            )

        # 🔧 修复音频画面不对齐问题：使用精确裁剪模式
        # 问题原因：
        #   1. -ss 在 -i 之前（input seeking）只能定位到最近的关键帧，导致每个片段时长不精确
        #   2. -c copy 流复制模式无法重新编码调整时长
        #   3. 多个片段拼接后，误差累积导致字幕与画面严重不对齐
        #
        # 解决方案：
        #   1. -ss 放在 -i 之后（output seeking）= 精确到毫秒级定位
        #   2. 使用 libx264 重新编码，确保输出时长与指定时长完全一致
        #   3. 使用 ultrafast 预设平衡速度和质量
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            source_url,
            "-ss",
            f"{start_ms / 1000:.3f}",  # 毫秒精度（output seeking，精确定位）
            "-t",
            f"{duration:.3f}",  # 毫秒精度
            "-c:v",
            "libx264",  # 视频重新编码（确保精确时长）
            "-preset",
            "ultrafast",  # 快速编码预设
            "-c:a",
            "aac",  # 音频重新编码
            "-b:a",
            "128k",  # 音频比特率
            target.as_posix(),
        ]

        try:
            logger.info(
                "twelvelabs.video_clip",
                video_id=video_id,
                target=target.as_posix(),
                source=source_url,
                is_local=is_local,
            )
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # 验证文件是否真的包含视频流
            # 使用 ffprobe 确认有有效视频流（不依赖文件大小判断）
            if target.exists():
                file_size = target.stat().st_size

                # 用 ffprobe 验证是否有视频流
                if self._verify_video_streams(target):
                    # 文件有效，记录大小供参考
                    if file_size < 50 * 1024:
                        logger.info(
                            "twelvelabs.clip_small_but_valid",
                            video_id=video_id,
                            file_size=file_size,
                            target=target.as_posix(),
                        )
                    return True

                # 有文件但没有视频流
                logger.warning(
                    "twelvelabs.clip_no_streams",
                    video_id=video_id,
                    file_size=file_size,
                    target=target.as_posix(),
                )
                target.unlink()

        except FileNotFoundError:
            logger.error("ffmpeg.not_found", cmd=cmd)
        except subprocess.CalledProcessError as exc:  # noqa: BLE001
            # 输出 FFmpeg 的错误信息以便诊断
            stderr_output = exc.stderr if exc.stderr else ""
            # 只输出最后几行关键错误
            error_lines = stderr_output.strip().split("\n")[-5:] if stderr_output else []
            logger.error(
                "twelvelabs.clip_failed",
                video_id=video_id,
                returncode=exc.returncode,
                ffmpeg_error=error_lines,
            )
        return False

    def _get_video_duration_ms(self, source_url: str) -> int | None:
        """使用 ffprobe 获取视频时长（毫秒）。

        Args:
            source_url: 视频文件路径或 URL

        Returns:
            视频时长（毫秒），获取失败返回 None
        """
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            source_url,
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
                duration_seconds = float(result.stdout.strip())
                return int(duration_seconds * 1000)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ffprobe.duration_failed", source=source_url, error=str(exc))
        return None

    def _cut_clip_with_loop(self, source_url: str, duration: float, target: Path, video_id: str) -> bool:
        """使用循环模式裁剪视频（当起始时间超出视频时长时）。

        FFmpeg -stream_loop 参数会循环输入流，从头开始裁剪所需时长。

        Args:
            source_url: 视频文件路径或 URL
            duration: 需要裁剪的时长（秒）
            target: 输出文件路径
            video_id: 视频 ID（用于日志）

        Returns:
            是否成功
        """
        cmd = [
            "ffmpeg",
            "-y",
            "-stream_loop", "-1",  # 无限循环输入流
            "-i", source_url,
            "-t", f"{duration:.3f}",  # 从头裁剪指定时长
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-b:a", "128k",
            target.as_posix(),
        ]

        try:
            logger.info(
                "twelvelabs.video_clip_loop",
                video_id=video_id,
                target=target.as_posix(),
                source=source_url,
                duration=duration,
            )
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # 验证输出文件
            if target.exists() and self._verify_video_streams(target):
                return True

            logger.warning("twelvelabs.clip_loop_failed", video_id=video_id, target=target.as_posix())
            if target.exists():
                target.unlink()

        except subprocess.CalledProcessError as exc:  # noqa: BLE001
            stderr_output = exc.stderr if exc.stderr else ""
            error_lines = stderr_output.strip().split("\n")[-5:] if stderr_output else []
            logger.error(
                "twelvelabs.clip_loop_failed",
                video_id=video_id,
                returncode=exc.returncode,
                ffmpeg_error=error_lines,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("twelvelabs.clip_loop_exception", video_id=video_id, error=str(exc))

        return False

    def _verify_video_streams(self, video_path: Path) -> bool:
        """使用 ffprobe 验证视频文件是否包含有效的视频流。"""
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path.as_posix(),
        ]
        try:
            result = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # 如果输出包含 "video"，说明有视频流
            return "video" in result.stdout.lower()
        except Exception as exc:  # noqa: BLE001
            logger.error("ffprobe.verify_failed", path=video_path.as_posix(), error=str(exc))
            return False

    def _get_video_lock(self, video_id: str) -> threading.Semaphore:
        with self._locks_lock:
            if video_id not in self._per_video_locks:
                self._per_video_locks[video_id] = threading.Semaphore(self._settings.render_per_video_limit)
            return self._per_video_locks[video_id]


video_fetcher = TwelveLabsVideoFetcher()

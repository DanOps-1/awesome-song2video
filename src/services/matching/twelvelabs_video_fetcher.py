"""TwelveLabs 视频素材下载工具。

支持直接从 HLS 流按时间窗拉取片段，避免全量下载。
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import structlog
from twelvelabs import TwelveLabs
from twelvelabs.core.api_error import ApiError
from twelvelabs.errors import NotFoundError

from src.infra.config.settings import AppSettings, get_settings

logger = structlog.get_logger(__name__)


class TwelveLabsVideoFetcher:
    """基于 retrieve API 下载视频片段，不落本地全量文件。"""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._live_enabled = bool(self._settings.tl_live_enabled)
        self._client: TwelveLabs | None = None
        if self._live_enabled:
            self._init_client()
        self._stream_cache: dict[str, str] = {}
        self._locks_lock = threading.Lock()
        self._per_video_locks: dict[str, threading.Semaphore] = {}

    def fetch_clip(self, video_id: str, start_ms: int, end_ms: int, target: Path) -> Path | None:
        """按时间窗拉取视频片段到目标路径（仅临时使用，不保留全量文件）。"""
        target.parent.mkdir(parents=True, exist_ok=True)
        start_ms = max(0, start_ms)
        end_ms = max(end_ms, start_ms + 500)

        # 优先实时拉取 HLS 片段
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
                    # 只尝试 -c copy（快速，不重新编码）
                    # 如果失败，返回 None 触发候选片段回退
                    if self._cut_clip(stream_url, start_ms, end_ms, target, video_id, use_reencode=False):
                        return target
                    # 不再回退到重新编码，让上层尝试下一个候选片段
            finally:
                lock.release()

        # 回退：若本地已有手动放置的全量文件，则从本地截取
        local_source = Path(self._settings.video_asset_dir) / f"{video_id}.mp4"
        if local_source.exists():
            if self._cut_clip(local_source.as_posix(), start_ms, end_ms, target, video_id, is_local=True):
                return target

        logger.warning("twelvelabs.clip_unavailable", video_id=video_id, start_ms=start_ms, end_ms=end_ms)
        return None

    def _init_client(self) -> None:
        """初始化 TwelveLabs SDK 客户端。"""
        try:
            self._client = TwelveLabs(api_key=self._settings.tl_api_key)
            logger.info("twelvelabs.sdk_initialized")
        except Exception as exc:  # noqa: BLE001
            logger.error("twelvelabs.sdk_init_failed", error=str(exc))
            self._client = None

    def _get_stream_url(self, video_id: str) -> str | None:
        """使用 SDK 获取视频的 HLS 流 URL。"""
        if video_id in self._stream_cache:
            return self._stream_cache[video_id]

        if not self._client:
            logger.error("twelvelabs.sdk_not_initialized")
            return None

        try:
            video = self._client.indexes.videos.retrieve(
                index_id=self._settings.tl_index_id,
                video_id=video_id,
            )
            logger.info("twelvelabs.retrieve_success", video_id=video_id)

            # 优先使用 HLS URL
            stream_url = None
            if hasattr(video, "hls") and video.hls:
                if hasattr(video.hls, "video_url"):
                    stream_url = str(video.hls.video_url)

            # 回退到直接 video_url（如果有）
            if not stream_url and hasattr(video, "video_url"):
                stream_url = str(video.video_url)

            if not stream_url:
                logger.error("twelvelabs.video_url_missing", video_id=video_id)
                return None

            self._stream_cache[video_id] = stream_url
            return stream_url

        except NotFoundError:
            logger.error("twelvelabs.video_not_found", video_id=video_id)
            return None
        except ApiError as exc:
            logger.error("twelvelabs.api_error", video_id=video_id, error=str(exc))
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("twelvelabs.retrieve_exception", video_id=video_id, error=str(exc))
            return None

    def _cut_clip(
        self,
        source_url: str,
        start_ms: int,
        end_ms: int,
        target: Path,
        video_id: str,
        *,
        is_local: bool = False,
        use_reencode: bool = False,
    ) -> bool:
        duration = max((end_ms - start_ms) / 1000.0, 0.5)

        # 构建 FFmpeg 命令
        cmd = ["ffmpeg", "-y"]

        # 如果是 HLS 流（非本地文件），在 -i 之前添加网络参数
        # 注意：reconnect 参数必须在 -i 之前
        if not is_local and (source_url.startswith("http://") or source_url.startswith("https://")):
            cmd.extend([
                "-reconnect", "1",              # 启用重连
                "-reconnect_streamed", "1",     # 对流媒体也启用重连
                "-reconnect_delay_max", "5",    # 最多延迟 5 秒重连
            ])

        # 对于 HLS 流，-ss 必须放在 -i 之后
        # 因为 HLS 不支持在 demuxer 层面快速 seek
        cmd.extend(["-i", source_url, "-ss", f"{start_ms / 1000:.2f}", "-t", f"{duration:.2f}"])

        # 编码策略：优先使用 -c copy，失败时回退到重新编码
        if use_reencode:
            # 使用快速编码参数，在质量和速度之间平衡
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "veryfast",  # 最快的编码速度
                "-crf", "18",           # 高质量（18 比默认 23 更高）
                "-c:a", "aac",
                "-b:a", "128k",
            ])
        else:
            cmd.extend(["-c", "copy"])

        cmd.append(target.as_posix())

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

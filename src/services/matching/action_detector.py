"""视频动作高光检测服务。

提供视频动作检测功能，用于实现画面与音乐的卡点对齐。
支持两种检测方式：
1. TwelveLabs Summarize API (高精度)
2. FFmpeg 场景检测 (备选)
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from anyio import to_thread

from src.domain.models.beat_sync import VideoActionCache
from src.infra.config.settings import get_settings
from src.infra.persistence.database import get_session

logger = structlog.get_logger(__name__)


@dataclass
class ActionPoint:
    """视频动作高光点。"""

    video_id: str
    timestamp_ms: int  # 动作发生时间
    confidence: float  # 置信度 (0-1)
    action_type: str  # 动作类型描述
    duration_ms: int  # 动作持续时间


@dataclass
class VideoActionProfile:
    """视频动作分析档案。"""

    video_id: str
    action_points: list[ActionPoint]
    scene_changes: list[int]  # 场景切换时间点（毫秒）
    analysis_source: str  # "twelvelabs" or "ffmpeg"


class ActionDetector:
    """视频动作检测器。"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._memory_cache: dict[str, VideoActionProfile] = {}

    async def analyze_video(
        self,
        video_id: str,
        force_refresh: bool = False,
    ) -> VideoActionProfile | None:
        """分析视频，提取动作高光和场景变化。

        策略：
        1. 检查内存缓存
        2. 检查数据库缓存
        3. 尝试使用 TwelveLabs Summarize API 获取 highlights
        4. 若不可用，使用本地 FFmpeg 场景检测作为备选

        Args:
            video_id: TwelveLabs 视频 ID
            force_refresh: 是否强制重新分析

        Returns:
            VideoActionProfile 或 None
        """
        # 1. 检查内存缓存
        if not force_refresh and video_id in self._memory_cache:
            return self._memory_cache[video_id]

        # 2. 检查数据库缓存
        if not force_refresh:
            cached = await self._load_from_db(video_id)
            if cached:
                self._memory_cache[video_id] = cached
                return cached

        # 3. 尝试 TwelveLabs 分析
        profile = None
        if self._settings.beat_sync_use_twelvelabs_highlights:
            profile = await self._analyze_with_twelvelabs(video_id)

        # 4. 备选：FFmpeg 场景检测
        if profile is None and self._settings.beat_sync_fallback_scene_detection:
            profile = await self._analyze_with_ffmpeg(video_id)

        # 保存到缓存
        if profile:
            self._memory_cache[video_id] = profile
            await self._save_to_db(profile)

        return profile

    async def _load_from_db(self, video_id: str) -> VideoActionProfile | None:
        """从数据库加载缓存的分析结果。"""
        try:
            async with get_session() as session:
                from sqlmodel import select

                stmt = select(VideoActionCache).where(VideoActionCache.video_id == video_id)
                result = await session.execute(stmt)
                cached = result.scalar_one_or_none()

                if cached:
                    action_points = [
                        ActionPoint(
                            video_id=video_id,
                            timestamp_ms=ap.get("timestamp_ms", 0),
                            confidence=ap.get("confidence", 0.5),
                            action_type=ap.get("action_type", "unknown"),
                            duration_ms=ap.get("duration_ms", 500),
                        )
                        for ap in (cached.action_points or [])
                    ]

                    return VideoActionProfile(
                        video_id=video_id,
                        action_points=action_points,
                        scene_changes=cached.scene_changes or [],
                        analysis_source=cached.analysis_source,
                    )
        except Exception as exc:
            logger.warning(
                "action_detector.db_load_failed",
                video_id=video_id,
                error=str(exc),
            )

        return None

    async def _save_to_db(self, profile: VideoActionProfile) -> None:
        """保存分析结果到数据库。"""
        try:
            async with get_session() as session:
                from sqlmodel import select

                # 检查是否已存在
                stmt = select(VideoActionCache).where(VideoActionCache.video_id == profile.video_id)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                action_points_data = [
                    {
                        "timestamp_ms": ap.timestamp_ms,
                        "confidence": ap.confidence,
                        "action_type": ap.action_type,
                        "duration_ms": ap.duration_ms,
                    }
                    for ap in profile.action_points
                ]

                if existing:
                    existing.action_points = action_points_data
                    existing.scene_changes = profile.scene_changes
                    existing.analysis_source = profile.analysis_source
                    existing.analyzed_at = datetime.utcnow()
                else:
                    cache = VideoActionCache(
                        video_id=profile.video_id,
                        action_points=action_points_data,
                        scene_changes=profile.scene_changes,
                        analysis_source=profile.analysis_source,
                        analyzed_at=datetime.utcnow(),
                    )
                    session.add(cache)

                await session.commit()

        except Exception as exc:
            logger.warning(
                "action_detector.db_save_failed",
                video_id=profile.video_id,
                error=str(exc),
            )

    async def _analyze_with_twelvelabs(self, video_id: str) -> VideoActionProfile | None:
        """使用 TwelveLabs Generate API 分析视频高光。"""
        try:
            from twelvelabs import (
                BadRequestError,
                ForbiddenError,
                InternalServerError,
                NotFoundError,
                TooManyRequestsError,
                TwelveLabs,
            )

            client = TwelveLabs(api_key=self._settings.tl_api_key)

            # 调用 generate API 获取 highlights
            def _call_api() -> Any:
                return client.generate.summarize(  # type: ignore[attr-defined]
                    video_id=video_id,
                    type="highlight",
                    prompt="Identify all action moments, movement changes, scene transitions, and visually impactful scenes with precise timestamps.",
                )

            result = await to_thread.run_sync(_call_api)

            action_points = []
            if hasattr(result, "highlights") and result.highlights:
                for h in result.highlights:
                    start_time = getattr(h, "start", 0)
                    end_time = getattr(h, "end", start_time + 0.5)
                    action_points.append(
                        ActionPoint(
                            video_id=video_id,
                            timestamp_ms=int(start_time * 1000),
                            confidence=getattr(h, "score", 0.8),
                            action_type=getattr(h, "highlight", "action"),
                            duration_ms=int((end_time - start_time) * 1000),
                        )
                    )

            # 如果没有 highlights 属性，尝试从 summary 提取
            if not action_points and hasattr(result, "summary"):
                logger.info(
                    "action_detector.no_highlights_using_summary",
                    video_id=video_id,
                )

            logger.info(
                "action_detector.twelvelabs_success",
                video_id=video_id,
                action_count=len(action_points),
            )

            return VideoActionProfile(
                video_id=video_id,
                action_points=action_points,
                scene_changes=[],
                analysis_source="twelvelabs",
            )

        except ForbiddenError as exc:
            # 认证错误
            logger.error(
                "action_detector.twelvelabs_auth_error",
                video_id=video_id,
                error=str(exc),
                error_type="ForbiddenError",
            )
            return None
        except NotFoundError as exc:
            # 视频不存在
            logger.warning(
                "action_detector.twelvelabs_video_not_found",
                video_id=video_id,
                error=str(exc),
                error_type="NotFoundError",
            )
            return None
        except BadRequestError as exc:
            # 请求参数错误
            logger.warning(
                "action_detector.twelvelabs_bad_request",
                video_id=video_id,
                error=str(exc),
                error_type="BadRequestError",
            )
            return None
        except TooManyRequestsError as exc:
            # 频率限制
            logger.warning(
                "action_detector.twelvelabs_rate_limit",
                video_id=video_id,
                error=str(exc),
                error_type="TooManyRequestsError",
            )
            return None
        except InternalServerError as exc:
            # 服务端错误
            logger.error(
                "action_detector.twelvelabs_server_error",
                video_id=video_id,
                error=str(exc),
                error_type="InternalServerError",
            )
            return None
        except Exception as exc:
            # 其他错误（网络等）
            logger.warning(
                "action_detector.twelvelabs_failed",
                video_id=video_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None

    async def _analyze_with_ffmpeg(self, video_id: str) -> VideoActionProfile | None:
        """使用 FFmpeg 场景检测作为备选方案。

        通过检测视频中的场景变化点来识别动作高光。
        """
        # 尝试多个可能的视频路径
        video_paths = [
            Path(self._settings.video_asset_dir) / f"{video_id}.mp4",
            Path(self._settings.video_asset_dir) / video_id / "video.mp4",
        ]

        video_path = None
        for p in video_paths:
            if p.exists():
                video_path = p
                break

        if not video_path:
            logger.warning(
                "action_detector.video_not_found",
                video_id=video_id,
                searched_paths=[str(p) for p in video_paths],
            )
            return None

        threshold = self._settings.beat_sync_scene_threshold

        # FFmpeg 场景检测命令
        cmd = [
            "ffmpeg",
            "-i",
            video_path.as_posix(),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-f",
            "null",
            "-",
        ]

        try:

            def _run_ffmpeg() -> list[int]:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                scene_times = []
                # 解析 showinfo 输出中的时间戳
                for line in result.stderr.split("\n"):
                    if "pts_time:" in line:
                        try:
                            # 提取 pts_time 后面的数值
                            pts_part = line.split("pts_time:")[1]
                            pts_time = float(pts_part.split()[0])
                            scene_times.append(int(pts_time * 1000))
                        except (IndexError, ValueError):
                            continue

                return scene_times

            scene_changes = await to_thread.run_sync(_run_ffmpeg)

            # 将场景切换转换为动作点
            action_points = [
                ActionPoint(
                    video_id=video_id,
                    timestamp_ms=t,
                    confidence=0.6,  # FFmpeg 检测置信度较低
                    action_type="scene_change",
                    duration_ms=500,
                )
                for t in scene_changes
            ]

            logger.info(
                "action_detector.ffmpeg_success",
                video_id=video_id,
                scene_count=len(scene_changes),
            )

            return VideoActionProfile(
                video_id=video_id,
                action_points=action_points,
                scene_changes=scene_changes,
                analysis_source="ffmpeg",
            )

        except subprocess.TimeoutExpired:
            logger.warning(
                "action_detector.ffmpeg_timeout",
                video_id=video_id,
            )
            return None
        except Exception as exc:
            logger.warning(
                "action_detector.ffmpeg_failed",
                video_id=video_id,
                error=str(exc),
            )
            return None

    def get_actions_in_range(
        self,
        profile: VideoActionProfile,
        start_ms: int,
        end_ms: int,
    ) -> list[ActionPoint]:
        """获取指定时间范围内的动作点。

        Args:
            profile: 视频动作分析档案
            start_ms: 起始时间（毫秒）
            end_ms: 结束时间（毫秒）

        Returns:
            时间范围内的动作点列表
        """
        return [ap for ap in profile.action_points if start_ms <= ap.timestamp_ms < end_ms]

    def get_nearest_action(
        self,
        profile: VideoActionProfile,
        target_ms: int,
        max_offset_ms: int = 1000,
    ) -> ActionPoint | None:
        """找到最接近目标时间的动作点。

        Args:
            profile: 视频动作分析档案
            target_ms: 目标时间（毫秒）
            max_offset_ms: 最大允许偏移（毫秒）

        Returns:
            最近的动作点或 None
        """
        if not profile.action_points:
            return None

        nearest = min(
            profile.action_points,
            key=lambda ap: abs(ap.timestamp_ms - target_ms),
        )

        if abs(nearest.timestamp_ms - target_ms) <= max_offset_ms:
            return nearest

        return None


# 单例实例
action_detector = ActionDetector()

"""CLIP 视频检索器 - 实现统一检索接口"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import structlog

from src.retrieval.protocol import VideoClip
from src.retrieval.clip.embedder import CLIPEmbedder
from src.retrieval.clip.database import CLIPDatabase, ShotRecord
from src.video.shot_detector import ShotDetector
from src.video.utils import extract_frames, get_video_metadata
from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)


class CLIPRetriever:
    """CLIP 视频检索器

    实现 VideoRetriever 协议，提供：
    - 本地视频索引
    - CLIP 视觉-文本编码
    - Qdrant 向量检索
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._embedder = CLIPEmbedder(
            model_name=settings.clip_model_name,
            device=settings.clip_device,
        )
        self._database = CLIPDatabase(
            db_path=settings.qdrant_path,
            collection_name=settings.qdrant_collection + "_clip",
        )
        self._shot_detector = ShotDetector(
            model_path=settings.transnet_model_path,
        )

    async def search(
        self,
        query: str,
        limit: int = 5,
        duration_hint_ms: Optional[int] = None,
    ) -> List[VideoClip]:
        """搜索视频片段

        Args:
            query: 搜索查询文本
            limit: 返回结果数量上限
            duration_hint_ms: 期望时长提示

        Returns:
            匹配的视频片段列表
        """
        # 编码查询文本
        query_vector = self._embedder.embed_text(query)

        # 搜索向量数据库
        results = self._database.search(
            query_vector=query_vector.tolist(),
            limit=limit * 2,  # 多取一些用于过滤
        )

        # 转换为 VideoClip 格式
        clips = []
        for item in results:
            start_ms = int(item["start_time"] * 1000)
            end_ms = int(item["end_time"] * 1000)

            clip = VideoClip(
                video_id=item["video_name"],
                start_ms=start_ms,
                end_ms=end_ms,
                score=item["score"],
                metadata={"text": item.get("text", "")},
            )

            # 时长过滤
            if duration_hint_ms:
                clip_duration = clip.duration_ms
                if clip_duration < duration_hint_ms * 0.3:
                    continue

            clips.append(clip)

            if len(clips) >= limit:
                break

        logger.info(
            "clip_retriever.search",
            query=query[:50],
            result_count=len(clips),
        )

        return clips

    async def index_video(self, video_path: str) -> int:
        """索引视频文件

        Args:
            video_path: 视频文件路径

        Returns:
            索引的镜头数量
        """
        video_path = Path(video_path)
        video_name = video_path.stem

        # 检测镜头
        shots = self._shot_detector.detect_shots(str(video_path))
        if not shots:
            logger.warning("clip_retriever.no_shots", video=video_name)
            return 0

        # 获取视频元数据
        metadata = get_video_metadata(video_path)
        if not metadata:
            return 0
        fps = metadata["fps"]

        # 为每个镜头生成嵌入
        records = []
        for start_frame, end_frame in shots:
            # 采样 8 帧
            frame_count = 8
            step = max(1, (end_frame - start_frame) // frame_count)
            sample_indices = [
                min(start_frame + i * step, end_frame - 1) for i in range(frame_count)
            ]

            frames = extract_frames(str(video_path), sample_indices)
            if frames.size == 0:
                continue

            # 编码
            vector = self._embedder.embed_shot(frames)

            # 计算时间
            start_time = start_frame / fps
            end_time = end_frame / fps

            records.append(
                ShotRecord(
                    video_name=video_name,
                    start_time=start_time,
                    end_time=end_time,
                    vector=vector.tolist(),
                )
            )

        # 存储到数据库
        self._database.add_shots(records)

        logger.info(
            "clip_retriever.indexed",
            video=video_name,
            shot_count=len(records),
        )

        return len(records)

    def supports_indexing(self) -> bool:
        """是否支持本地索引"""
        return True

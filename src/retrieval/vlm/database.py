"""VLM 向量数据库

使用 Qdrant 存储视频镜头的描述向量。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class VLMShotRecord:
    """VLM 镜头记录"""

    video_name: str
    start_time: float
    end_time: float
    description: str
    vector: List[float]
    start_frame: int = 0
    end_frame: int = 0
    frame_indices: List[int] = field(default_factory=list)


class VLMDatabase:
    """VLM 向量数据库

    存储视频镜头的语义描述向量，支持文本检索。
    """

    def __init__(
        self,
        db_path: str = "data/qdrant",
        collection_name: str = "vlm_shots",
        embedding_dim: int = 768,
    ):
        """初始化数据库

        Args:
            db_path: Qdrant 数据存储路径
            collection_name: 集合名称
            embedding_dim: 嵌入向量维度
        """
        self.db_path = db_path
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.client = None

    def _connect(self) -> None:
        """连接数据库"""
        if self.client is not None:
            return

        from qdrant_client import QdrantClient

        Path(self.db_path).mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=self.db_path)
        self._ensure_collection()
        logger.info("vlm_database.connected", path=self.db_path)

    def _ensure_collection(self) -> None:
        """确保集合存在"""
        from qdrant_client.models import Distance, VectorParams

        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "vlm_database.collection_created",
                name=self.collection_name,
                dim=self.embedding_dim,
            )

    def add_shots(self, shots: List[VLMShotRecord]) -> None:
        """添加镜头记录

        Args:
            shots: 镜头记录列表
        """
        if not shots:
            return

        from qdrant_client.models import PointStruct

        self._connect()

        collection_info = self.client.get_collection(self.collection_name)
        start_id = collection_info.points_count

        points = [
            PointStruct(
                id=start_id + i,
                vector=shot.vector,
                payload={
                    "video_name": shot.video_name,
                    "start_time": shot.start_time,
                    "end_time": shot.end_time,
                    "description": shot.description,
                    "start_frame": shot.start_frame,
                    "end_frame": shot.end_frame,
                    "frame_indices": shot.frame_indices,
                },
            )
            for i, shot in enumerate(shots)
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info("vlm_database.shots_added", count=len(points))

    def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        video_filter: Optional[str] = None,
    ) -> List[dict]:
        """搜索相似镜头

        Args:
            query_vector: 查询向量
            limit: 返回结果数量
            video_filter: 可选的视频名称过滤

        Returns:
            匹配结果列表
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        self._connect()

        query_filter = None
        if video_filter:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="video_name",
                        match=MatchValue(value=video_filter),
                    )
                ]
            )

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
        )

        return [
            {
                "video_name": r.payload.get("video_name", ""),
                "start_time": r.payload.get("start_time", 0.0),
                "end_time": r.payload.get("end_time", 0.0),
                "description": r.payload.get("description", ""),
                "score": r.score,
            }
            for r in results.points
        ]

    def get_all_shots(self, video_name: Optional[str] = None) -> List[dict]:
        """获取所有镜头

        Args:
            video_name: 可选的视频名称过滤

        Returns:
            镜头列表
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        self._connect()

        query_filter = None
        if video_name:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="video_name",
                        match=MatchValue(value=video_name),
                    )
                ]
            )

        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=query_filter,
            limit=10000,
        )

        return [
            {
                "shot_id": r.id,
                "payload": r.payload,
            }
            for r in results[0]
        ]

    def delete_by_video(self, video_name: str) -> None:
        """删除指定视频的所有镜头

        Args:
            video_name: 视频名称
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        self._connect()

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="video_name",
                        match=MatchValue(value=video_name),
                    )
                ]
            ),
        )
        logger.info("vlm_database.video_deleted", video=video_name)

    def count(self) -> int:
        """获取总镜头数"""
        self._connect()
        info = self.client.get_collection(self.collection_name)
        return info.points_count

    def clear(self) -> None:
        """清空数据库"""
        self._connect()
        self.client.delete_collection(self.collection_name)
        self._ensure_collection()
        logger.info("vlm_database.cleared", collection=self.collection_name)

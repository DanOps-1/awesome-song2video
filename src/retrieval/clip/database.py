"""CLIP 向量数据库

使用 Qdrant 本地存储进行向量检索。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ShotRecord:
    """视频镜头记录"""

    video_name: str
    start_time: float
    end_time: float
    vector: List[float]
    text: Optional[str] = None


class CLIPDatabase:
    """CLIP 向量数据库

    使用 Qdrant 本地持久化存储，无需运行服务器。
    """

    def __init__(
        self,
        db_path: str = "data/qdrant",
        collection_name: str = "clip_shots",
        embedding_dim: int = 768,
    ):
        """初始化数据库

        Args:
            db_path: Qdrant 数据存储路径
            collection_name: 集合名称
            embedding_dim: 嵌入向量维度
        """
        from qdrant_client import QdrantClient

        self.db_path = db_path
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.client = QdrantClient(path=db_path)
        self._ensure_collection()

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
                "clip_database.collection_created",
                name=self.collection_name,
                dim=self.embedding_dim,
            )

    def add_shots(self, shots: List[ShotRecord]) -> None:
        """添加镜头记录

        Args:
            shots: 镜头记录列表
        """
        if not shots:
            return

        from qdrant_client.models import PointStruct

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
                    "text": shot.text or "",
                },
            )
            for i, shot in enumerate(shots)
        ]

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info("clip_database.shots_added", count=len(points))

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
                "text": r.payload.get("text", ""),
                "score": r.score,
            }
            for r in results.points
        ]

    def delete_by_video(self, video_name: str) -> None:
        """删除指定视频的所有镜头

        Args:
            video_name: 视频名称
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

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
        logger.info("clip_database.video_deleted", video=video_name)

    def count(self) -> int:
        """获取总镜头数"""
        info = self.client.get_collection(self.collection_name)
        return info.points_count

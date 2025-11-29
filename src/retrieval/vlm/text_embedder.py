"""VLM 文本嵌入模块

使用 sentence-transformers 将文本转换为向量表示。
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class TextEmbedder:
    """文本嵌入器

    使用 multilingual-e5-base 模型，支持中英文。
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-base",
        device: Optional[str] = None,
    ):
        """初始化文本嵌入器

        Args:
            model_name: 模型名称
            device: 计算设备
        """
        self.model_name = model_name
        self._device = device
        self.model = None
        self._embedding_dim = None

    @property
    def device(self) -> str:
        if self._device:
            return self._device
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"

    def load_model(self) -> None:
        """延迟加载模型"""
        if self.model is not None:
            return

        from sentence_transformers import SentenceTransformer

        logger.info("text_embedder.loading", model=self.model_name)
        self.model = SentenceTransformer(self.model_name, device=self.device)
        self._embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(
            "text_embedder.loaded",
            device=self.device,
            dim=self._embedding_dim,
        )

    def embed_query(self, query: str) -> np.ndarray:
        """编码查询文本

        Args:
            query: 查询文本

        Returns:
            归一化向量
        """
        self.load_model()

        # e5 模型查询使用 query 前缀
        if "e5" in self.model_name.lower():
            query = f"query: {query}"

        vec = self.model.encode(query, normalize_embeddings=True)
        return vec

    def embed_document(self, doc: str) -> np.ndarray:
        """编码文档文本（用于索引）

        Args:
            doc: 文档文本

        Returns:
            归一化向量
        """
        self.load_model()

        # e5 模型文档使用 passage 前缀
        if "e5" in self.model_name.lower():
            doc = f"passage: {doc}"

        vec = self.model.encode(doc, normalize_embeddings=True)
        return vec

    def embed_batch(
        self,
        texts: List[str],
        is_query: bool = False,
        show_progress: bool = False,
    ) -> np.ndarray:
        """批量编码文本

        Args:
            texts: 文本列表
            is_query: 是否为查询文本
            show_progress: 是否显示进度条

        Returns:
            (N, dim) 形状的向量数组
        """
        self.load_model()

        # e5 模型添加前缀
        if "e5" in self.model_name.lower():
            prefix = "query: " if is_query else "passage: "
            texts = [f"{prefix}{t}" for t in texts]

        vecs = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
        )
        return vecs

    def get_embedding_dim(self) -> int:
        """获取嵌入维度"""
        self.load_model()
        return self._embedding_dim

    @staticmethod
    def compute_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        return float(np.dot(vec1, vec2))

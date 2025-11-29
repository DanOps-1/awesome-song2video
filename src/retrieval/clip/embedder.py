"""CLIP 视觉-文本嵌入器

使用 OpenCLIP ViT-L-14 模型进行视觉和文本编码。
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class CLIPEmbedder:
    """OpenCLIP 嵌入器

    使用 ViT-L-14 模型（OpenAI 预训练权重）生成 768 维嵌入向量。
    支持视频帧和文本的联合编码。
    """

    def __init__(
        self,
        model_name: str = "ViT-L-14",
        pretrained: str = "openai",
        device: Optional[str] = None,
    ):
        """初始化 CLIP 嵌入器

        Args:
            model_name: 模型名称，默认 ViT-L-14
            pretrained: 预训练权重，默认 openai
            device: 计算设备，默认自动选择
        """
        self.model_name = model_name
        self.pretrained = pretrained
        self._device = device
        self.model = None
        self.preprocess = None
        self.tokenizer = None

    @property
    def device(self) -> str:
        if self._device:
            return self._device
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"

    def load_model(self) -> None:
        """加载 CLIP 模型"""
        if self.model is not None:
            return

        import torch
        import open_clip
        from PIL import Image

        try:
            logger.info("clip.loading_model", model=self.model_name)
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_name, pretrained=self.pretrained
            )
            self.tokenizer = open_clip.get_tokenizer(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info("clip.model_loaded", device=self.device)
        except Exception as e:
            logger.error("clip.load_failed", error=str(e))
            raise

    def _normalize(self, vec: np.ndarray) -> np.ndarray:
        """L2 归一化"""
        norm = np.linalg.norm(vec)
        if norm > 0:
            return vec / norm
        return vec

    def embed_shot(self, frames: np.ndarray) -> np.ndarray:
        """编码视频镜头

        通过平均多帧嵌入获得镜头级别的表示。

        Args:
            frames: 帧数组 (N, H, W, C)，dtype=uint8

        Returns:
            768 维归一化向量
        """
        import torch
        from PIL import Image

        self.load_model()

        try:
            frame_embeddings = []

            for frame in frames:
                pil_image = Image.fromarray(frame)
                image_input = self.preprocess(pil_image).unsqueeze(0).to(self.device)

                with torch.no_grad():
                    features = self.model.encode_image(image_input)
                    features = features / features.norm(dim=-1, keepdim=True)
                    frame_embeddings.append(features.cpu().numpy().flatten())

            avg_embedding = np.mean(frame_embeddings, axis=0)
            return self._normalize(avg_embedding)

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                logger.error("clip.gpu_oom")
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            raise

    def embed_text(self, text: str) -> np.ndarray:
        """编码文本查询

        Args:
            text: 查询文本

        Returns:
            768 维归一化向量
        """
        import torch

        self.load_model()

        try:
            text_tokens = self.tokenizer([text]).to(self.device)
            with torch.no_grad():
                text_features = self.model.encode_text(text_tokens)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            vec = text_features.cpu().numpy().flatten()
            return self._normalize(vec)
        except Exception as e:
            logger.error("clip.text_embed_failed", error=str(e))
            raise

    def get_embedding_dim(self) -> int:
        """获取嵌入维度"""
        return 768

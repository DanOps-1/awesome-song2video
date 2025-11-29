"""统一视频检索模块

支持多种检索后端：
- TwelveLabs: 云端多模态搜索 API
- CLIP: 本地视觉-文本联合编码
- VLM: VLM 描述生成 + 文本嵌入
"""

from src.retrieval.protocol import VideoClip, VideoRetriever
from src.retrieval.factory import create_retriever

__all__ = ["VideoClip", "VideoRetriever", "create_retriever"]

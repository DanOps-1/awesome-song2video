"""视频检索器工厂"""

from typing import Optional

from src.retrieval.protocol import VideoRetriever


def create_retriever(backend: Optional[str] = None) -> VideoRetriever:
    """创建视频检索器实例

    Args:
        backend: 检索后端类型，可选值：
            - "twelvelabs": TwelveLabs 云端 API
            - "clip": 本地 CLIP 视觉编码 + Qdrant
            - "vlm": VLM 描述生成 + 文本嵌入 + Qdrant
            如果为 None，则从配置中读取默认值

    Returns:
        实现 VideoRetriever 协议的检索器实例

    Raises:
        ValueError: 如果指定了未知的后端类型
    """
    from src.infra.config.settings import settings

    backend = backend or settings.retriever_backend

    if backend == "twelvelabs":
        from src.retrieval.twelvelabs import TwelveLabsRetriever

        return TwelveLabsRetriever()
    elif backend == "clip":
        from src.retrieval.clip import CLIPRetriever

        return CLIPRetriever()
    elif backend == "vlm":
        from src.retrieval.vlm import VLMRetriever

        return VLMRetriever()
    else:
        raise ValueError(f"Unknown retriever backend: {backend}")

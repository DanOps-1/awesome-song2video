"""视频检索器工厂

TwelveLabs-only architecture - CLIP and VLM backends removed.
"""

from src.retrieval.protocol import VideoRetriever


def create_retriever() -> VideoRetriever:
    """创建 TwelveLabs 视频检索器实例

    Returns:
        TwelveLabsRetriever 实例
    """
    from src.retrieval.twelvelabs import TwelveLabsRetriever

    return TwelveLabsRetriever()

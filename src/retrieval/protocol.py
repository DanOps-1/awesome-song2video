"""统一视频检索接口定义"""

from dataclasses import dataclass, field
from typing import Protocol, List, Optional, runtime_checkable


@dataclass
class VideoClip:
    """视频片段候选结果"""

    video_id: str
    start_ms: int
    end_ms: int
    score: float
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        """片段时长（毫秒）"""
        return self.end_ms - self.start_ms


@runtime_checkable
class VideoRetriever(Protocol):
    """视频检索统一接口

    所有检索后端（TwelveLabs、CLIP、VLM）都必须实现此协议。
    """

    async def search(
        self,
        query: str,
        limit: int = 5,
        duration_hint_ms: Optional[int] = None,
    ) -> List[VideoClip]:
        """根据文本查询搜索视频片段

        Args:
            query: 搜索查询文本
            limit: 返回结果数量上限
            duration_hint_ms: 期望的片段时长提示（毫秒），用于过滤或排序

        Returns:
            匹配的视频片段列表，按相关性降序排列
        """
        ...

    async def index_video(self, video_path: str) -> int:
        """索引视频文件

        Args:
            video_path: 视频文件路径

        Returns:
            索引的片段数量

        Raises:
            NotImplementedError: 如果后端不支持本地索引
        """
        ...

    def supports_indexing(self) -> bool:
        """是否支持本地索引

        Returns:
            True 如果支持本地索引（如 CLIP、VLM），
            False 如果不支持（如 TwelveLabs 使用云端索引）
        """
        ...

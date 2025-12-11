"""VLM 视频描述生成模块

使用多模态大模型（Claude/GPT）对视频镜头生成语义描述。
"""

from __future__ import annotations

import base64
import io
from typing import List, Optional

import numpy as np
import requests
import structlog
from PIL import Image

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)


class VLMCaptioner:
    """VLM 视频描述生成器

    使用多模态大模型对视频镜头生成语义丰富的描述。
    支持多帧分析，能够捕捉镜头内的动态变化。
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """初始化 VLM 描述器

        Args:
            model_name: 模型名称
            endpoint: API 端点
            api_key: API 密钥
        """
        settings = get_settings()
        self.model_name = model_name or settings.vlm_model
        self.endpoint = endpoint or settings.vlm_endpoint
        self.api_key = api_key or settings.vlm_api_key
        self.timeout = 180

        logger.info(
            "vlm_captioner.initialized",
            model=self.model_name,
            endpoint=self.endpoint[:30] if self.endpoint else None,
        )

    def _frame_to_base64(self, frame: np.ndarray, quality: int = 80) -> str:
        """将 numpy 图像转换为 base64 字符串"""
        if len(frame.shape) == 2:
            frame = np.stack([frame] * 3, axis=-1)
        elif frame.shape[-1] == 4:
            frame = frame[:, :, :3]

        img = Image.fromarray(frame.astype(np.uint8))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def caption_shot(
        self,
        frames: List[np.ndarray],
        start_time: float = 0,
        end_time: float = 0,
        prompt: Optional[str] = None,
    ) -> str:
        """对视频镜头生成描述

        Args:
            frames: 帧列表，建议 3-5 帧
            start_time: 镜头开始时间（秒）
            end_time: 镜头结束时间（秒）
            prompt: 自定义提示词

        Returns:
            镜头描述文本
        """
        if not frames:
            return ""

        if prompt is None:
            if len(frames) == 1:
                prompt = (
                    "描述这个画面中你看到的内容。\n\n"
                    "重点关注：\n"
                    "- 画面中实际存在的视觉元素\n"
                    "- 具体的颜色、形状、物体\n"
                    "- 如果有角色：外观特征和动作\n"
                    "- 画面的整体风格或氛围\n\n"
                    "用中文回答，150-250字，描述要具体。"
                )
            else:
                prompt = (
                    f"这是一个视频镜头的 {len(frames)} 帧截图"
                    f"（从 {start_time:.1f}秒 到 {end_time:.1f}秒）。\n\n"
                    "描述这个镜头中你看到的内容。\n\n"
                    "重点关注：\n"
                    "- 画面中实际存在的视觉元素\n"
                    "- 角色的外观特征和动作变化\n"
                    "- 场景或物品的具体描述\n\n"
                    "用中文回答，150-250字。"
                )

        return self._call_api(frames, prompt)

    def _call_api(self, frames: List[np.ndarray], prompt: str) -> str:
        """通过 API 调用模型"""
        content = []
        for frame in frames:
            img_b64 = self._frame_to_base64(frame)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
            })
        content.append({"type": "text", "text": prompt})

        try:
            response = requests.post(
                self.endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": content}],
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if "choices" in data:
                return data["choices"][0]["message"]["content"]
            elif "response" in data:
                candidates = data["response"]["candidates"]
                return candidates[0]["content"]["parts"][0]["text"]
            else:
                raise ValueError(f"Unknown response format: {data}")

        except requests.exceptions.Timeout:
            logger.error("vlm_captioner.timeout")
            raise
        except Exception as e:
            logger.error("vlm_captioner.api_failed", error=str(e))
            raise

    @staticmethod
    def get_num_keyframes(duration_sec: float, fps_target: float = 2.0) -> int:
        """根据镜头时长计算关键帧数量

        Args:
            duration_sec: 镜头时长（秒）
            fps_target: 目标采样率（帧/秒）

        Returns:
            关键帧数量（3-15 帧）
        """
        return min(15, max(3, int(duration_sec * fps_target)))

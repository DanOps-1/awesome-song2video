"""镜头检测模块 - 使用 TransNetV2 神经网络检测视频镜头边界"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import structlog

from src.video.utils import extract_frames, get_video_metadata

logger = structlog.get_logger(__name__)


class ShotDetector:
    """使用 TransNetV2 进行镜头边界检测。

    TransNetV2 是专门用于视频镜头检测的神经网络，
    能够识别视频中的切镜、淡入淡出等转场效果。

    Example:
        >>> detector = ShotDetector()
        >>> shots = detector.detect_shots("video.mp4")
        >>> for start, end in shots:
        ...     print(f"镜头: {start} - {end}")
    """

    def __init__(self, model_path: Optional[str] = None):
        """初始化镜头检测器。

        Args:
            model_path: TransNetV2 模型路径，默认使用 models/transnetv2
        """
        if model_path is None:
            # 默认模型路径
            self.model_path = str(Path(__file__).parent.parent.parent / "models" / "transnetv2")
        else:
            self.model_path = model_path
        self.model = None

    def load_model(self) -> None:
        """加载 TransNetV2 模型。"""
        if self.model is not None:
            return

        # 强制使用 CPU 避免 CuDNN 版本问题
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

        import tensorflow as tf

        if not os.path.exists(self.model_path):
            logger.error("shot_detector.model_not_found", path=self.model_path)
            raise FileNotFoundError(f"模型未找到: {self.model_path}")

        try:
            self.model = tf.saved_model.load(self.model_path)
            logger.info("shot_detector.model_loaded", path=self.model_path)
        except Exception as e:
            logger.error("shot_detector.load_failed", error=str(e))
            raise

    def detect_shots(
        self,
        video_path: str | Path,
        threshold: float = 0.5,
        batch_size: Optional[int] = None,
    ) -> list[tuple[int, int]]:
        """检测视频中的镜头边界。

        Args:
            video_path: 视频文件路径
            threshold: 镜头边界判定阈值 (0-1)，默认 0.5
            batch_size: 批处理大小，默认从环境变量 TRANSNET_BATCH 读取或使用 32

        Returns:
            镜头列表 [(start_frame, end_frame), ...]
        """
        self.load_model()

        metadata = get_video_metadata(video_path)
        if not metadata:
            return []

        total_frames = metadata["total_frames"]
        logger.info(
            "shot_detector.detecting",
            path=str(video_path),
            total_frames=total_frames,
        )

        # 批处理参数
        if batch_size is None:
            batch_size = int(os.environ.get("TRANSNET_BATCH", 32))
        input_height, input_width = 27, 48

        all_predictions = []

        for i in range(0, total_frames, batch_size):
            batch_indices = list(range(i, min(i + batch_size, total_frames)))
            if not batch_indices:
                break

            frames = extract_frames(str(video_path), batch_indices)
            if frames.size == 0:
                continue

            # 预处理：resize 到 27x48
            processed = []
            for frame in frames:
                resized = cv2.resize(frame, (input_width, input_height))
                processed.append(resized)

            # 构建输入张量 [1, Batch, 27, 48, 3]
            input_tensor = np.array(processed, dtype=np.float32)[np.newaxis, ...]

            # 推理
            try:
                predictions = self.model(input_tensor)

                # 处理不同的返回格式
                pred = None
                if isinstance(predictions, dict):
                    for key in ["logits", "predictions", "output_0"]:
                        if key in predictions:
                            pred = predictions[key]
                            break
                    if pred is None:
                        pred = list(predictions.values())[0]
                elif isinstance(predictions, (list, tuple)):
                    pred = predictions[0]
                else:
                    pred = predictions

                if hasattr(pred, "numpy"):
                    pred_np = pred.numpy().flatten()
                else:
                    pred_np = np.array(pred).flatten()

                all_predictions.extend(pred_np)

            except Exception as e:
                logger.error("shot_detector.inference_failed", batch=i, error=str(e))
                raise

        # 后处理：阈值判定镜头边界
        predictions_array = np.array(all_predictions)
        boundary_indices = np.where(predictions_array > threshold)[0]

        # 构建镜头列表
        shots = []
        start = 0
        for boundary in boundary_indices:
            if boundary > start:
                shots.append((start, boundary))
            start = boundary + 1

        # 添加最后一个镜头
        if start < total_frames:
            shots.append((start, total_frames))

        logger.info("shot_detector.detected", shot_count=len(shots))
        return shots

    def get_shot_keyframes(
        self,
        shot: tuple[int, int],
        num_frames: int = 3,
    ) -> list[int]:
        """获取镜头的关键帧索引。

        Args:
            shot: (start_frame, end_frame)
            num_frames: 提取的关键帧数量

        Returns:
            关键帧索引列表
        """
        start, end = shot
        if end - start <= num_frames:
            return list(range(start, end))

        # 均匀分布提取关键帧
        indices = np.linspace(start, end - 1, num_frames, dtype=int)
        return indices.tolist()

    def get_shots_with_timestamps(
        self,
        video_path: str | Path,
        threshold: float = 0.5,
    ) -> list[dict]:
        """检测镜头并返回带时间戳的结果。

        Args:
            video_path: 视频文件路径
            threshold: 镜头边界判定阈值

        Returns:
            镜头列表，每个镜头包含:
            - start_frame: 起始帧
            - end_frame: 结束帧
            - start_time: 起始时间（秒）
            - end_time: 结束时间（秒）
            - duration: 时长（秒）
        """
        metadata = get_video_metadata(video_path)
        if not metadata:
            return []

        fps = metadata["fps"]
        shots = self.detect_shots(video_path, threshold)

        results = []
        for start_frame, end_frame in shots:
            start_time = start_frame / fps
            end_time = end_frame / fps
            results.append({
                "start_frame": start_frame,
                "end_frame": end_frame,
                "start_time": start_time,
                "end_time": end_time,
                "duration": end_time - start_time,
            })

        return results

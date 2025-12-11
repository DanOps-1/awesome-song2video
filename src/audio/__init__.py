"""音频处理模块

提供以下功能：
- transcriber: Whisper 语音转录
- vocal_detector: RMS 能量分析和人声检测
- audio_cutter: 音频裁剪工具
- preprocessor: 音频预处理（Demucs人声分离 + DeepFilterNet去噪）
- structure_analyzer: 基于歌词时长的 intro/outro 检测
"""

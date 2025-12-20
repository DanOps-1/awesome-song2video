"""节拍对齐器单元测试。"""

from __future__ import annotations

import pytest

from src.audio.beat_detector import BeatAnalysisResult
from src.services.matching.beat_aligner import BeatAligner


@pytest.fixture
def beat_aligner() -> BeatAligner:
    """创建节拍对齐器实例。"""
    return BeatAligner()


@pytest.fixture
def stable_beats() -> BeatAnalysisResult:
    """创建稳定节拍的分析结果。"""
    return BeatAnalysisResult(
        bpm=120.0,
        beat_times_ms=[0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000],
        downbeat_times_ms=[0, 2000, 4000],
        beat_strength=[1.0, 0.5, 0.6, 0.5, 1.0, 0.5, 0.6, 0.5, 1.0],
        tempo_stability=0.95,
    )


@pytest.fixture
def unstable_beats() -> BeatAnalysisResult:
    """创建不稳定节拍的分析结果。"""
    return BeatAnalysisResult(
        bpm=100.0,
        beat_times_ms=[0, 400, 1100, 1400, 2200],
        downbeat_times_ms=[0, 2200],
        beat_strength=[1.0, 0.5, 0.6, 0.5, 1.0],
        tempo_stability=0.3,  # 低稳定性
    )


class TestShouldApplyBeatSync:
    """测试 should_apply_beat_sync 方法。"""

    def test_returns_true_for_stable_beats(
        self, beat_aligner: BeatAligner, stable_beats: BeatAnalysisResult
    ) -> None:
        """测试稳定节拍返回 True。"""
        assert beat_aligner.should_apply_beat_sync(stable_beats) is True

    def test_returns_false_for_unstable_beats(
        self, beat_aligner: BeatAligner, unstable_beats: BeatAnalysisResult
    ) -> None:
        """测试不稳定节拍返回 False。"""
        assert beat_aligner.should_apply_beat_sync(unstable_beats) is False

    def test_returns_false_for_none_beats(self, beat_aligner: BeatAligner) -> None:
        """测试 None 返回 False。"""
        assert beat_aligner.should_apply_beat_sync(None) is False

    def test_returns_false_for_too_few_beats(self, beat_aligner: BeatAligner) -> None:
        """测试节拍太少返回 False。"""
        few_beats = BeatAnalysisResult(
            bpm=120.0,
            beat_times_ms=[0, 500, 1000],  # 只有3个节拍
            downbeat_times_ms=[0],
            beat_strength=[1.0, 0.5, 0.6],
            tempo_stability=1.0,
        )
        assert beat_aligner.should_apply_beat_sync(few_beats) is False

    def test_custom_stability_threshold(
        self, beat_aligner: BeatAligner, unstable_beats: BeatAnalysisResult
    ) -> None:
        """测试自定义稳定性阈值。"""
        # 使用更低的阈值，应该返回 True
        assert beat_aligner.should_apply_beat_sync(unstable_beats, min_stability=0.2) is True


class TestAdjustClipTiming:
    """测试 adjust_clip_timing 方法。"""

    def test_applies_positive_offset(self, beat_aligner: BeatAligner) -> None:
        """测试应用正偏移（提前播放）。"""
        new_start, new_end = beat_aligner.adjust_clip_timing(
            clip_start_ms=1000,
            clip_end_ms=2000,
            offset_ms=100,
        )
        assert new_start == 900
        assert new_end == 1900

    def test_applies_negative_offset(self, beat_aligner: BeatAligner) -> None:
        """测试应用负偏移（延后播放）。"""
        new_start, new_end = beat_aligner.adjust_clip_timing(
            clip_start_ms=1000,
            clip_end_ms=2000,
            offset_ms=-100,
        )
        assert new_start == 1100
        assert new_end == 2100

    def test_preserves_duration(self, beat_aligner: BeatAligner) -> None:
        """测试保持时长不变。"""
        new_start, new_end = beat_aligner.adjust_clip_timing(
            clip_start_ms=1000,
            clip_end_ms=3000,
            offset_ms=200,
        )
        assert new_end - new_start == 2000  # 原始时长

    def test_clamps_to_zero(self, beat_aligner: BeatAligner) -> None:
        """测试不会小于0。"""
        new_start, new_end = beat_aligner.adjust_clip_timing(
            clip_start_ms=100,
            clip_end_ms=1100,
            offset_ms=500,  # 会导致负数
        )
        assert new_start == 0
        assert new_end == 1000

    def test_clamps_to_source_duration(self, beat_aligner: BeatAligner) -> None:
        """测试不会超出源视频时长。"""
        new_start, new_end = beat_aligner.adjust_clip_timing(
            clip_start_ms=4000,
            clip_end_ms=5000,
            offset_ms=-500,  # 会导致超出
            source_duration_ms=5000,
        )
        assert new_end <= 5000

    def test_zero_offset_unchanged(self, beat_aligner: BeatAligner) -> None:
        """测试零偏移不改变。"""
        new_start, new_end = beat_aligner.adjust_clip_timing(
            clip_start_ms=1000,
            clip_end_ms=2000,
            offset_ms=0,
        )
        assert new_start == 1000
        assert new_end == 2000

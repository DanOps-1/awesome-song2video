"""节拍检测器单元测试。"""

from __future__ import annotations

import pytest

from src.audio.beat_detector import (
    BeatAnalysisResult,
    find_nearest_beat,
    find_nearest_downbeat,
    get_beat_at_index,
    get_beat_interval_ms,
    get_beats_in_range,
    _calculate_tempo_stability,
    _estimate_downbeats,
)


@pytest.fixture
def sample_beats() -> BeatAnalysisResult:
    """创建测试用的节拍分析结果。"""
    return BeatAnalysisResult(
        bpm=120.0,  # 每分钟120拍，每拍500ms
        beat_times_ms=[0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000],
        downbeat_times_ms=[0, 2000, 4000],  # 每4拍一个强拍
        beat_strength=[1.0, 0.5, 0.6, 0.5, 1.0, 0.5, 0.6, 0.5, 1.0],
        tempo_stability=0.95,
    )


class TestGetBeatsInRange:
    """测试 get_beats_in_range 函数。"""

    def test_returns_beats_within_range(self, sample_beats: BeatAnalysisResult) -> None:
        """测试返回指定范围内的节拍。"""
        result = get_beats_in_range(sample_beats, 1000, 2500)
        assert result == [1000, 1500, 2000]

    def test_returns_empty_for_no_beats_in_range(self, sample_beats: BeatAnalysisResult) -> None:
        """测试范围内无节拍时返回空列表。"""
        result = get_beats_in_range(sample_beats, 5000, 6000)
        assert result == []

    def test_excludes_end_boundary(self, sample_beats: BeatAnalysisResult) -> None:
        """测试结束边界不包含在内。"""
        result = get_beats_in_range(sample_beats, 0, 500)
        assert result == [0]
        assert 500 not in result


class TestFindNearestBeat:
    """测试 find_nearest_beat 函数。"""

    def test_finds_exact_beat(self, sample_beats: BeatAnalysisResult) -> None:
        """测试精确匹配节拍。"""
        result = find_nearest_beat(sample_beats, 1000)
        assert result == (1000, 0)

    def test_finds_nearest_before(self, sample_beats: BeatAnalysisResult) -> None:
        """测试找到之前最近的节拍。"""
        result = find_nearest_beat(sample_beats, 1100)
        assert result == (1000, -100)

    def test_finds_nearest_after(self, sample_beats: BeatAnalysisResult) -> None:
        """测试找到之后最近的节拍。"""
        result = find_nearest_beat(sample_beats, 1400)
        assert result == (1500, 100)

    def test_returns_none_when_too_far(self, sample_beats: BeatAnalysisResult) -> None:
        """测试偏移超过阈值时返回 None。"""
        result = find_nearest_beat(sample_beats, 1000, max_offset_ms=50)
        assert result == (1000, 0)  # 精确匹配

        result = find_nearest_beat(sample_beats, 1300, max_offset_ms=50)
        assert result is None  # 超出阈值

    def test_returns_none_for_empty_beats(self) -> None:
        """测试空节拍列表返回 None。"""
        empty_beats = BeatAnalysisResult(
            bpm=120.0,
            beat_times_ms=[],
            downbeat_times_ms=[],
            beat_strength=[],
            tempo_stability=0.0,
        )
        result = find_nearest_beat(empty_beats, 1000)
        assert result is None


class TestFindNearestDownbeat:
    """测试 find_nearest_downbeat 函数。"""

    def test_finds_exact_downbeat(self, sample_beats: BeatAnalysisResult) -> None:
        """测试精确匹配强拍。"""
        result = find_nearest_downbeat(sample_beats, 2000)
        assert result == (2000, 0)

    def test_finds_nearest_downbeat(self, sample_beats: BeatAnalysisResult) -> None:
        """测试找到最近的强拍。"""
        result = find_nearest_downbeat(sample_beats, 1800)
        assert result == (2000, 200)

    def test_returns_none_when_too_far(self, sample_beats: BeatAnalysisResult) -> None:
        """测试偏移超过阈值时返回 None。"""
        result = find_nearest_downbeat(sample_beats, 1000, max_offset_ms=500)
        assert result is None


class TestEstimateDownbeats:
    """测试 _estimate_downbeats 函数。"""

    def test_returns_every_fourth_beat(self) -> None:
        """测试每4拍返回一个强拍。"""
        beat_times = [0, 500, 1000, 1500, 2000, 2500, 3000, 3500]
        result = _estimate_downbeats(beat_times, 120.0)
        assert result == [0, 2000]

    def test_returns_all_for_few_beats(self) -> None:
        """测试节拍数少于4时返回全部。"""
        beat_times = [0, 500, 1000]
        result = _estimate_downbeats(beat_times, 120.0)
        assert result == [0, 500, 1000]

    def test_returns_empty_for_empty_input(self) -> None:
        """测试空输入返回空列表。"""
        result = _estimate_downbeats([], 120.0)
        assert result == []


class TestCalculateTempoStability:
    """测试 _calculate_tempo_stability 函数。"""

    def test_perfect_stability_for_even_intervals(self) -> None:
        """测试完全均匀的间隔返回高稳定性。"""
        beat_times = [0, 500, 1000, 1500, 2000]
        result = _calculate_tempo_stability(beat_times)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_low_stability_for_uneven_intervals(self) -> None:
        """测试不均匀间隔返回低稳定性。"""
        beat_times = [0, 500, 800, 2000, 2200]
        result = _calculate_tempo_stability(beat_times)
        assert result < 0.8

    def test_returns_zero_for_single_beat(self) -> None:
        """测试单个节拍返回0。"""
        result = _calculate_tempo_stability([1000])
        assert result == 0.0

    def test_returns_zero_for_empty_list(self) -> None:
        """测试空列表返回0。"""
        result = _calculate_tempo_stability([])
        assert result == 0.0


class TestGetBeatAtIndex:
    """测试 get_beat_at_index 函数。"""

    def test_returns_beat_at_valid_index(self, sample_beats: BeatAnalysisResult) -> None:
        """测试有效索引返回节拍时间。"""
        assert get_beat_at_index(sample_beats, 0) == 0
        assert get_beat_at_index(sample_beats, 2) == 1000
        assert get_beat_at_index(sample_beats, 8) == 4000

    def test_returns_none_for_invalid_index(self, sample_beats: BeatAnalysisResult) -> None:
        """测试无效索引返回 None。"""
        assert get_beat_at_index(sample_beats, -1) is None
        assert get_beat_at_index(sample_beats, 100) is None


class TestGetBeatIntervalMs:
    """测试 get_beat_interval_ms 函数。"""

    def test_calculates_correct_interval(self, sample_beats: BeatAnalysisResult) -> None:
        """测试计算正确的节拍间隔。"""
        # 120 BPM = 500ms per beat
        result = get_beat_interval_ms(sample_beats)
        assert result == pytest.approx(500.0)

    def test_returns_zero_for_zero_bpm(self) -> None:
        """测试 BPM 为 0 时返回 0。"""
        zero_bpm_beats = BeatAnalysisResult(
            bpm=0.0,
            beat_times_ms=[],
            downbeat_times_ms=[],
            beat_strength=[],
            tempo_stability=0.0,
        )
        result = get_beat_interval_ms(zero_bpm_beats)
        assert result == 0.0

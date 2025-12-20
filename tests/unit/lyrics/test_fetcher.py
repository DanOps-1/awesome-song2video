"""歌词获取器单元测试。"""

from __future__ import annotations

import pytest

from src.lyrics.fetcher import (
    LyricLine,
    parse_lrc,
    parse_lrc_time,
)


class TestParseLrcTime:
    """测试 parse_lrc_time 函数。"""

    def test_parses_standard_format(self) -> None:
        """测试标准格式 [mm:ss.xx]。"""
        result = parse_lrc_time("01:23.45")
        assert result == pytest.approx(83.45, abs=0.01)

    def test_parses_with_milliseconds(self) -> None:
        """测试带毫秒格式 [mm:ss.xxx]。"""
        result = parse_lrc_time("00:30.500")
        assert result == pytest.approx(30.5, abs=0.001)

    def test_parses_single_digit_ms(self) -> None:
        """测试单位数毫秒。"""
        result = parse_lrc_time("00:10.5")
        assert result == pytest.approx(10.5, abs=0.01)

    def test_parses_two_digit_ms(self) -> None:
        """测试两位数毫秒。"""
        result = parse_lrc_time("00:10.50")
        assert result == pytest.approx(10.5, abs=0.01)

    def test_parses_zero_time(self) -> None:
        """测试零时间。"""
        result = parse_lrc_time("00:00.00")
        assert result == pytest.approx(0.0)


class TestParseLrc:
    """测试 parse_lrc 函数。"""

    def test_parses_simple_lrc(self) -> None:
        """测试解析简单 LRC 文本。"""
        lrc_text = """[00:10.00]第一句歌词
[00:15.50]第二句歌词
[00:20.00]第三句歌词"""

        result = parse_lrc(lrc_text)

        assert len(result) == 3
        assert result[0].text == "第一句歌词"
        assert result[0].start_time == pytest.approx(10.0)
        assert result[0].end_time == pytest.approx(15.5)
        assert result[1].text == "第二句歌词"
        assert result[2].text == "第三句歌词"

    def test_skips_metadata_lines(self) -> None:
        """测试跳过元数据行。"""
        lrc_text = """[00:00.00]作词：张三
[00:00.01]作曲：李四
[00:10.00]第一句歌词"""

        result = parse_lrc(lrc_text)

        assert len(result) == 1
        assert result[0].text == "第一句歌词"

    def test_returns_empty_for_empty_input(self) -> None:
        """测试空输入返回空列表。"""
        assert parse_lrc("") == []
        assert parse_lrc(None) == []  # type: ignore[arg-type]

    def test_skips_empty_lines(self) -> None:
        """测试跳过空文本行。"""
        lrc_text = """[00:10.00]第一句
[00:15.00]
[00:20.00]第二句"""

        result = parse_lrc(lrc_text)

        assert len(result) == 2
        assert result[0].text == "第一句"
        assert result[1].text == "第二句"

    def test_sets_end_time_for_last_line(self) -> None:
        """测试最后一行设置默认结束时间。"""
        lrc_text = "[00:10.00]唯一的歌词"

        result = parse_lrc(lrc_text)

        assert len(result) == 1
        assert result[0].end_time == pytest.approx(15.0)  # start_time + 5.0

    def test_sorts_by_start_time(self) -> None:
        """测试按开始时间排序。"""
        lrc_text = """[00:20.00]第三句
[00:10.00]第一句
[00:15.00]第二句"""

        result = parse_lrc(lrc_text)

        assert result[0].start_time == pytest.approx(10.0)
        assert result[1].start_time == pytest.approx(15.0)
        assert result[2].start_time == pytest.approx(20.0)


class TestLyricLine:
    """测试 LyricLine 数据类。"""

    def test_creates_with_required_fields(self) -> None:
        """测试创建只有必填字段的实例。"""
        line = LyricLine(start_time=10.0, end_time=15.0, text="测试歌词")

        assert line.start_time == 10.0
        assert line.end_time == 15.0
        assert line.text == "测试歌词"

    def test_allows_none_end_time(self) -> None:
        """测试允许 end_time 为 None。"""
        line = LyricLine(start_time=10.0, end_time=None, text="测试")

        assert line.end_time is None

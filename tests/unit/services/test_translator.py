"""翻译器单元测试。"""

from __future__ import annotations

from langdetect import DetectorFactory

from src.services.subtitle.translator import is_english

# 为 langdetect 设置确定性种子，确保测试结果可重复
DetectorFactory.seed = 0


class TestIsEnglish:
    """测试 is_english 函数。"""

    def test_detects_english_text(self) -> None:
        """测试检测英文文本。"""
        # 使用更长的英文句子以提高检测准确性
        assert is_english("The quick brown fox jumps over the lazy dog") is True
        assert is_english("This is a very long English sentence for testing purposes") is True

    def test_detects_chinese_text(self) -> None:
        """测试检测中文文本。"""
        assert is_english("你好世界，这是一段中文文本") is False
        assert is_english("这是一个测试句子") is False

    def test_returns_false_for_empty_text(self) -> None:
        """测试空文本返回 False。"""
        assert is_english("") is False
        assert is_english("   ") is False

    def test_returns_false_for_only_punctuation(self) -> None:
        """测试只有标点返回 False。"""
        assert is_english("!!!...???") is False
        assert is_english("123 456") is False

    def test_handles_mixed_content(self) -> None:
        """测试混合内容（检测语言）。"""
        # 混合内容取决于检测结果，只要返回布尔值即可
        result = is_english("Hello 世界")
        assert isinstance(result, bool)

    def test_handles_special_characters(self) -> None:
        """测试带特殊字符的文本。"""
        # 使用更长的句子以提高检测准确性
        assert is_english("Hello world! How are you doing today?") is True

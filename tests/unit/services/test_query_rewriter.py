"""查询改写器单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.services.matching.query_rewriter import QueryRewriter


def _create_rewriter_disabled() -> QueryRewriter:
    """创建一个禁用 LLM 的改写器实例。"""
    with patch("src.services.matching.query_rewriter.get_settings") as mock_settings:
        mock_settings.return_value = SimpleNamespace(
            query_rewrite_enabled=False,
            deepseek_api_key=None,
            deepseek_base_url="https://api.deepseek.com/v1",
        )
        return QueryRewriter()


class TestContainsCharacter:
    """测试 _contains_character 方法。"""

    def test_detects_cat(self) -> None:
        """测试检测 cat。"""
        rewriter = _create_rewriter_disabled()
        assert rewriter._contains_character("cat is chasing mouse") is True
        assert rewriter._contains_character("Cat running") is True

    def test_detects_mouse(self) -> None:
        """测试检测 mouse。"""
        rewriter = _create_rewriter_disabled()
        assert rewriter._contains_character("mouse escaping") is True

    def test_detects_cat_keywords(self) -> None:
        """测试检测猫相关关键词。"""
        rewriter = _create_rewriter_disabled()
        assert rewriter._contains_character("the cat is sleeping") is True
        assert rewriter._contains_character("cute kitten") is True
        assert rewriter._contains_character("feline creature") is True

    def test_detects_mouse_keywords(self) -> None:
        """测试检测鼠相关关键词。"""
        rewriter = _create_rewriter_disabled()
        assert rewriter._contains_character("mouse running") is True
        assert rewriter._contains_character("rodent hiding") is True

    def test_detects_chinese_keywords(self) -> None:
        """测试检测中文关键词。"""
        rewriter = _create_rewriter_disabled()
        assert rewriter._contains_character("猫追老鼠") is True
        assert rewriter._contains_character("小老鼠逃跑") is True

    def test_returns_false_without_keywords(self) -> None:
        """测试不包含关键词返回 False。"""
        rewriter = _create_rewriter_disabled()
        assert rewriter._contains_character("sunset beach scene") is False
        assert rewriter._contains_character("music playing") is False


class TestEnsureCharacterInQuery:
    """测试 _ensure_character_in_query 方法。"""

    def test_returns_unchanged_if_has_character(self) -> None:
        """测试已包含角色时不修改。"""
        rewriter = _create_rewriter_disabled()
        query = "cat chasing something"
        result = rewriter._ensure_character_in_query(query)
        assert result == query

    def test_adds_prefix_if_no_character(self) -> None:
        """测试不包含角色时添加前缀。"""
        rewriter = _create_rewriter_disabled()
        query = "sunset scene"
        result = rewriter._ensure_character_in_query(query)
        assert result == "cat and mouse sunset scene"

    def test_preserves_original_content(self) -> None:
        """测试保留原始内容。"""
        rewriter = _create_rewriter_disabled()
        query = "action scene with explosion"
        result = rewriter._ensure_character_in_query(query)
        assert "action scene with explosion" in result

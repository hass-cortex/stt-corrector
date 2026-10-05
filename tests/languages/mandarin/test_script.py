"""Tests for ChineseScriptConverter."""

from custom_components.stt_corrector.correction.languages.mandarin import (
    ChineseScriptConverter,
)
from custom_components.stt_corrector.correction.types import CorrectionMethod


class TestChineseScriptConverterS2TW:
    """Tests for simplified -> traditional (Taiwan) conversion."""

    def test_converts_simplified_to_traditional(self) -> None:
        converter = ChineseScriptConverter("s2tw")
        result, changes = converter.process("开灯")
        assert result == "開燈"
        assert len(changes) == 1
        assert changes[0].method == CorrectionMethod.SCRIPT_CONVERSION

    def test_character_level_conversion(self) -> None:
        """s2tw should convert characters without phrase-level substitution."""
        converter = ChineseScriptConverter("s2tw")
        result, _ = converter.process("打开换气扇")
        assert result == "打開換氣扇"

    def test_no_change_returns_empty_changes(self) -> None:
        converter = ChineseScriptConverter("s2tw")
        result, changes = converter.process("開燈")
        assert result == "開燈"
        assert changes == []

    def test_empty_text(self) -> None:
        converter = ChineseScriptConverter("s2tw")
        result, changes = converter.process("")
        assert result == ""
        assert changes == []

    def test_mixed_text_partial_conversion(self) -> None:
        converter = ChineseScriptConverter("s2tw")
        result, changes = converter.process("请开灯")
        assert "請" in result
        assert "開燈" in result
        assert len(changes) == 1

    def test_change_records_full_text(self) -> None:
        converter = ChineseScriptConverter("s2tw")
        _, changes = converter.process("开灯")
        assert changes[0].original_segment == "开灯"
        assert changes[0].corrected_segment == "開燈"
        assert changes[0].confidence == 1.0


class TestChineseScriptConverterT2S:
    """Tests for traditional -> simplified conversion."""

    def test_converts_traditional_to_simplified(self) -> None:
        converter = ChineseScriptConverter("t2s")
        result, changes = converter.process("開燈")
        assert result == "开灯"
        assert len(changes) == 1

    def test_no_change_when_already_simplified(self) -> None:
        converter = ChineseScriptConverter("t2s")
        result, changes = converter.process("开灯")
        assert result == "开灯"
        assert changes == []


class TestChineseScriptConverterS2HK:
    """Tests for simplified -> traditional (Hong Kong) conversion."""

    def test_converts_simplified_to_hk_traditional(self) -> None:
        converter = ChineseScriptConverter("s2hk")
        result, changes = converter.process("开灯")
        assert result == "開燈"
        assert len(changes) == 1

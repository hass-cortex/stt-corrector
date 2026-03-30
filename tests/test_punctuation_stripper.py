"""Tests for TrailingPunctuationStripper."""

from custom_components.stt_corrector.correction.processors.punctuation import (
    TrailingPunctuationStripper,
)
from custom_components.stt_corrector.correction.types import CorrectionMethod


class TestTrailingPunctuationStripper:
    """Tests for trailing punctuation stripping."""

    def test_strips_chinese_period(self) -> None:
        stripper = TrailingPunctuationStripper("。")
        result, changes = stripper.process("打开灯。")
        assert result == "打开灯"
        assert len(changes) == 1
        assert changes[0].method == CorrectionMethod.PUNCTUATION_STRIP

    def test_strips_question_mark(self) -> None:
        stripper = TrailingPunctuationStripper("。？")
        result, changes = stripper.process("今天天气如何？")
        assert result == "今天天气如何"
        assert len(changes) == 1

    def test_strips_multiple_trailing(self) -> None:
        stripper = TrailingPunctuationStripper("。")
        result, changes = stripper.process("开灯。。")
        assert result == "开灯"
        assert len(changes) == 1

    def test_no_trailing_punctuation(self) -> None:
        stripper = TrailingPunctuationStripper("。")
        result, changes = stripper.process("打开灯")
        assert result == "打开灯"
        assert changes == []

    def test_empty_text(self) -> None:
        stripper = TrailingPunctuationStripper("。")
        result, changes = stripper.process("")
        assert result == ""
        assert changes == []

    def test_empty_punctuation_string(self) -> None:
        stripper = TrailingPunctuationStripper("")
        result, changes = stripper.process("打开灯。")
        assert result == "打开灯。"
        assert changes == []

    def test_preserves_mid_sentence_punctuation(self) -> None:
        stripper = TrailingPunctuationStripper("。")
        result, changes = stripper.process("你好。开灯")
        assert result == "你好。开灯"
        assert changes == []

    def test_change_records_full_text(self) -> None:
        stripper = TrailingPunctuationStripper("。")
        _, changes = stripper.process("开灯。")
        assert changes[0].original_segment == "开灯。"
        assert changes[0].corrected_segment == "开灯"
        assert changes[0].confidence == 1.0

    def test_custom_punctuation_set(self) -> None:
        stripper = TrailingPunctuationStripper("。？！，")
        result, _ = stripper.process("关灯！")
        assert result == "关灯"

    def test_only_punctuation_text(self) -> None:
        """Text that is only punctuation should be stripped to empty."""
        stripper = TrailingPunctuationStripper("。")
        result, changes = stripper.process("。")
        assert result == ""
        assert len(changes) == 1

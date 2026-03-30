"""Tests for ReplacementProcessor."""

from custom_components.stt_corrector.correction.processors.replacement import (
    ReplacementProcessor,
)
from custom_components.stt_corrector.correction.types import CorrectionMethod


class TestReplacementProcessor:
    """Tests for custom replacement processing."""

    def test_single_replacement(self) -> None:
        rp = ReplacementProcessor({"bed room": "bedroom"})
        result, changes = rp.process("turn on bed room light")
        assert result == "turn on bedroom light"
        assert len(changes) == 1
        assert changes[0].method == CorrectionMethod.CUSTOM_RULE
        assert changes[0].confidence == 1.0

    def test_multiple_replacements(self) -> None:
        rp = ReplacementProcessor({"ABC": "XYZ", "hello": "world"})
        result, changes = rp.process("hello and ABC")
        assert "world" in result
        assert "XYZ" in result
        assert len(changes) == 2

    def test_longer_keys_applied_first(self) -> None:
        """Longer keys should match before shorter ones to prevent partial matches."""
        rp = ReplacementProcessor({"大門鎖": "lock", "大門鎖定": "locking"})
        result, _ = rp.process("大門鎖定系統")
        assert "locking" in result

    def test_no_rules_returns_unchanged(self) -> None:
        rp = ReplacementProcessor({})
        result, changes = rp.process("hello world")
        assert result == "hello world"
        assert changes == []

    def test_empty_text(self) -> None:
        rp = ReplacementProcessor({"hello": "world"})
        result, changes = rp.process("")
        assert result == ""
        assert changes == []

    def test_no_match_returns_unchanged(self) -> None:
        rp = ReplacementProcessor({"foo": "bar"})
        result, changes = rp.process("hello world")
        assert result == "hello world"
        assert changes == []

    def test_chinese_replacement(self) -> None:
        rp = ReplacementProcessor({"大門鎖": "大門鎖定"})
        result, changes = rp.process("打開大門鎖")
        assert result == "打開大門鎖定"
        assert len(changes) == 1

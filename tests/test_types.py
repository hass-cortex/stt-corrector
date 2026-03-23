"""Tests for STT correction data types."""

from custom_components.stt_corrector.correction.types import (
    CorrectionChange,
    CorrectionResult,
)


class TestCorrectionChange:
    """Tests for CorrectionChange dataclass."""

    def test_creation_with_all_fields(self) -> None:
        change = CorrectionChange(
            original_segment="循環三",
            corrected_segment="循環扇",
            method="homophone",
            confidence=1.0,
        )
        assert change.original_segment == "循環三"
        assert change.corrected_segment == "循環扇"
        assert change.method == "homophone"
        assert change.confidence == 1.0

    def test_fuzzy_match_confidence(self) -> None:
        change = CorrectionChange(
            original_segment="livng room",
            corrected_segment="living room",
            method="fuzzy_match",
            confidence=0.9,
        )
        assert change.confidence == 0.9
        assert change.method == "fuzzy_match"

    def test_custom_rule_method(self) -> None:
        change = CorrectionChange(
            original_segment="old",
            corrected_segment="new",
            method="custom_rule",
            confidence=1.0,
        )
        assert change.method == "custom_rule"

    def test_equality(self) -> None:
        a = CorrectionChange("a", "b", "homophone", 1.0)
        b = CorrectionChange("a", "b", "homophone", 1.0)
        assert a == b

    def test_inequality(self) -> None:
        a = CorrectionChange("a", "b", "homophone", 1.0)
        b = CorrectionChange("a", "c", "homophone", 1.0)
        assert a != b


class TestCorrectionResult:
    """Tests for CorrectionResult dataclass."""

    def test_creation_with_defaults(self) -> None:
        result = CorrectionResult(original="hello", corrected="hello")
        assert result.original == "hello"
        assert result.corrected == "hello"
        assert result.changes == []

    def test_creation_with_changes(self) -> None:
        change = CorrectionChange("循環三", "循環扇", "homophone", 1.0)
        result = CorrectionResult(
            original="打開循環三",
            corrected="打開循環扇",
            changes=[change],
        )
        assert len(result.changes) == 1
        assert result.changes[0].original_segment == "循環三"

    def test_multiple_changes(self) -> None:
        changes = [
            CorrectionChange("循環三", "循環扇", "homophone", 1.0),
            CorrectionChange("走廊等", "走廊燈", "homophone", 1.0),
        ]
        result = CorrectionResult(
            original="打開循環三和走廊等",
            corrected="打開循環扇和走廊燈",
            changes=changes,
        )
        assert len(result.changes) == 2

    def test_default_changes_not_shared(self) -> None:
        """Ensure default list is not shared between instances."""
        r1 = CorrectionResult(original="a", corrected="a")
        r2 = CorrectionResult(original="b", corrected="b")
        r1.changes.append(CorrectionChange("x", "y", "homophone", 1.0))
        assert len(r2.changes) == 0

    def test_equality(self) -> None:
        a = CorrectionResult(original="a", corrected="b", changes=[])
        b = CorrectionResult(original="a", corrected="b", changes=[])
        assert a == b

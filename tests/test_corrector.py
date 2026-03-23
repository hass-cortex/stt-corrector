"""Tests for SpeechCorrector two-stage pipeline."""

from custom_components.stt_corrector.correction.corrector import SpeechCorrector


class TestSpeechCorrectorChinese:
    """Tests for Chinese text correction."""

    def test_custom_replacement(self) -> None:
        """Stage 1: custom replacements should apply."""
        sc = SpeechCorrector(custom_replacements={"大門鎖": "大門鎖定"})
        result = sc.correct("打開大門鎖")
        assert result.corrected == "打開大門鎖定"
        assert len(result.changes) == 1
        assert result.changes[0].method == "custom_rule"

    def test_pinyin_fuzzy_match_homophones(self) -> None:
        """Stage 2: pinyin matching should catch Chinese homophones."""
        sc = SpeechCorrector(
            known_phrases=["循環扇"],
            fuzzy_threshold=0.75,
        )
        result = sc.correct("打開循環三")
        assert result.corrected == "打開循環扇"
        assert len(result.changes) == 1
        assert result.changes[0].method == "fuzzy_match"

    def test_pinyin_corrects_lamp_homophones(self) -> None:
        """Pinyin matching should correct lamp-related homophones."""
        sc = SpeechCorrector(
            known_phrases=["走廊燈"],
            fuzzy_threshold=0.75,
        )
        result = sc.correct("打開走廊等")
        assert "走廊燈" in result.corrected
        assert len(result.changes) == 1
        assert result.changes[0].method == "fuzzy_match"

    def test_pinyin_corrects_entrance_homophones(self) -> None:
        """Pinyin matching should correct entrance-related homophones."""
        sc = SpeechCorrector(
            known_phrases=["入口燈"],
            fuzzy_threshold=0.75,
        )
        result = sc.correct("路口燈")
        assert result.corrected == "入口燈"
        assert len(result.changes) == 1

    def test_no_change_needed(self) -> None:
        """Text that is already correct should not be changed."""
        sc = SpeechCorrector(known_phrases=["客廳燈"])
        result = sc.correct("打開客廳燈")
        assert result.corrected == "打開客廳燈"
        assert result.changes == []


class TestSpeechCorrectorEnglish:
    """Tests for English text correction."""

    def test_english_custom_replacement(self) -> None:
        sc = SpeechCorrector(custom_replacements={"bed room": "bedroom"})
        result = sc.correct("turn on bed room light")
        assert result.corrected == "turn on bedroom light"
        assert len(result.changes) == 1
        assert result.changes[0].method == "custom_rule"

    def test_english_fuzzy_match(self) -> None:
        sc = SpeechCorrector(
            known_phrases=["living room"],
            fuzzy_threshold=0.7,
        )
        result = sc.correct("turn on livng room light")
        assert "living room" in result.corrected
        assert len(result.changes) == 1
        assert result.changes[0].method == "fuzzy_match"

    def test_english_no_false_positive(self) -> None:
        """Should not incorrectly change unrelated words."""
        sc = SpeechCorrector(
            known_phrases=["kitchen"],
            fuzzy_threshold=0.75,
        )
        result = sc.correct("I like chicken")
        assert result.corrected == "I like chicken"
        assert result.changes == []


class TestSpeechCorrectorEdgeCases:
    """Edge case tests."""

    def test_update_phrases(self) -> None:
        sc = SpeechCorrector(
            known_phrases=["客廳燈"],
            fuzzy_threshold=0.6,
        )
        sc.update_phrases(["臥室燈"])
        result = sc.correct("臥室等")
        assert result.corrected == "臥室燈"
        assert len(result.changes) == 1

    def test_empty_text(self) -> None:
        sc = SpeechCorrector()
        result = sc.correct("")
        assert result.corrected == ""
        assert result.changes == []

    def test_both_stages_combine(self) -> None:
        """Both stages can each contribute corrections."""
        sc = SpeechCorrector(
            custom_replacements={"ABC": "XYZ"},
            known_phrases=["循環扇"],
            fuzzy_threshold=0.75,
        )
        # Custom: ABC -> XYZ
        # Pinyin: 循環三 -> 循環扇
        result = sc.correct("循環三和ABC")
        assert "循環扇" in result.corrected
        assert "XYZ" in result.corrected
        assert len(result.changes) == 2

    def test_disable_custom_replacements(self) -> None:
        """Custom replacements should be skipped when disabled."""
        sc = SpeechCorrector(
            custom_replacements={"大門鎖": "大門鎖定"},
            enable_custom_replacements=False,
        )
        result = sc.correct("打開大門鎖")
        assert result.corrected == "打開大門鎖"
        assert result.changes == []

    def test_disable_fuzzy_matching(self) -> None:
        """Fuzzy matching should be skipped when disabled."""
        sc = SpeechCorrector(
            known_phrases=["循環扇"],
            fuzzy_threshold=0.75,
            enable_fuzzy_matching=False,
        )
        result = sc.correct("打開循環三")
        assert result.corrected == "打開循環三"
        assert result.changes == []

    def test_disable_fuzzy_keeps_custom(self) -> None:
        """Disabling fuzzy should still apply custom replacements."""
        sc = SpeechCorrector(
            custom_replacements={"ABC": "XYZ"},
            known_phrases=["循環扇"],
            fuzzy_threshold=0.75,
            enable_fuzzy_matching=False,
        )
        result = sc.correct("循環三和ABC")
        assert "XYZ" in result.corrected
        assert "循環三" in result.corrected  # Not corrected
        assert len(result.changes) == 1
        assert result.changes[0].method == "custom_rule"

    def test_disable_custom_keeps_fuzzy(self) -> None:
        """Disabling custom should still apply fuzzy matching."""
        sc = SpeechCorrector(
            custom_replacements={"ABC": "XYZ"},
            known_phrases=["循環扇"],
            fuzzy_threshold=0.75,
            enable_custom_replacements=False,
        )
        result = sc.correct("循環三和ABC")
        assert "循環扇" in result.corrected
        assert "ABC" in result.corrected  # Not replaced
        assert len(result.changes) == 1
        assert result.changes[0].method == "fuzzy_match"

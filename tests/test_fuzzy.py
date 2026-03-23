"""Tests for FuzzyMatcher."""

from custom_components.stt_corrector.correction.fuzzy_matcher import FuzzyMatcher
from custom_components.stt_corrector.correction.matchers import PhoneticMatcher


class TestFuzzyMatcherChinese:
    """Tests for Chinese fuzzy matching (uses pinyin comparison)."""

    def test_chinese_homophone_match(self) -> None:
        """A homophone Chinese phrase should be corrected via pinyin."""
        fm = FuzzyMatcher(known_phrases=["走廊燈"], threshold=0.75)
        corrected, changes = fm.correct("走廊等")
        assert corrected == "走廊燈"
        assert len(changes) == 1
        assert changes[0].method == "fuzzy_match"
        assert changes[0].confidence >= 0.75

    def test_chinese_fan_homophone(self) -> None:
        """Fan homophones should be corrected."""
        fm = FuzzyMatcher(known_phrases=["循環扇"], threshold=0.75)
        corrected, changes = fm.correct("循環三")
        assert corrected == "循環扇"
        assert len(changes) == 1

    def test_chinese_entrance_homophone(self) -> None:
        """Entrance homophones should be corrected."""
        fm = FuzzyMatcher(known_phrases=["入口燈"], threshold=0.75)
        corrected, changes = fm.correct("路口燈")
        assert corrected == "入口燈"
        assert len(changes) == 1

    def test_chinese_curtain_homophone(self) -> None:
        """Curtain homophones should be corrected."""
        fm = FuzzyMatcher(known_phrases=["窗簾"], threshold=0.75)
        corrected, changes = fm.correct("窗連")
        assert corrected == "窗簾"
        assert len(changes) == 1

    def test_skip_already_correct(self) -> None:
        """Exact match should not produce a change."""
        fm = FuzzyMatcher(known_phrases=["客廳燈"], threshold=0.75)
        corrected, changes = fm.correct("客廳燈")
        assert corrected == "客廳燈"
        assert changes == []

    def test_skip_single_char_phrases(self) -> None:
        """Single character phrases should be ignored (too ambiguous)."""
        fm = FuzzyMatcher(known_phrases=["燈"], threshold=0.6)
        corrected, changes = fm.correct("等")
        assert corrected == "等"
        assert changes == []

    def test_below_threshold_rejected(self) -> None:
        """Unrelated text should not match."""
        fm = FuzzyMatcher(known_phrases=["客廳燈"], threshold=0.75)
        corrected, changes = fm.correct("廚房門")
        assert corrected == "廚房門"
        assert changes == []

    def test_longer_phrase_matched_first(self) -> None:
        """Longer known phrases should be matched before shorter ones."""
        fm = FuzzyMatcher(
            known_phrases=["客廳", "客廳大燈"],
            threshold=0.6,
        )
        corrected, changes = fm.correct("客廰大燈")
        assert corrected == "客廳大燈"
        assert len(changes) == 1
        assert changes[0].corrected_segment == "客廳大燈"

    def test_no_corrupt_substring_of_correct_phrase(self) -> None:
        """Fuzzy match must not replace a substring of an already-correct phrase.

        Regression: '關閉入口燈' with known phrases ['入口燈', '小燈']
        was wrongly correcting '口燈' → '小燈' because the sliding window
        matched a sub-part of the correct phrase '入口燈'.
        """
        fm = FuzzyMatcher(
            known_phrases=["入口燈", "小燈"],
            threshold=0.75,
        )
        corrected, changes = fm.correct("關閉入口燈。")
        assert corrected == "關閉入口燈。"
        assert changes == []

    def test_correct_phrase_protected_but_errors_still_fixed(self) -> None:
        """Correctly present phrases are protected, but other errors are fixed."""
        fm = FuzzyMatcher(
            known_phrases=["入口燈", "走廊燈"],
            threshold=0.75,
        )
        corrected, changes = fm.correct("關閉入口燈和走廊等")
        assert "入口燈" in corrected
        assert "走廊燈" in corrected
        assert len(changes) == 1
        assert changes[0].original_segment == "走廊等"


class TestFuzzyMatcherEnglish:
    """Tests for English fuzzy matching (uses SequenceMatcher)."""

    def test_english_typo_match(self) -> None:
        """An English typo should be corrected."""
        fm = FuzzyMatcher(known_phrases=["living room"], threshold=0.7)
        corrected, changes = fm.correct("turn on livng room light")
        assert "living room" in corrected
        assert len(changes) == 1

    def test_english_bedroom_typo(self) -> None:
        fm = FuzzyMatcher(known_phrases=["bedroom"], threshold=0.7)
        corrected, changes = fm.correct("turn on bedrom light")
        assert "bedroom" in corrected
        assert len(changes) == 1

    def test_chicken_not_kitchen(self) -> None:
        """'chicken' should not match 'kitchen' at a reasonable threshold."""
        fm = FuzzyMatcher(known_phrases=["kitchen"], threshold=0.75)
        corrected, changes = fm.correct("I like chicken")
        assert corrected == "I like chicken"
        assert changes == []

    def test_no_mid_word_cut(self) -> None:
        """English windows should snap to word boundaries."""
        fm = FuzzyMatcher(known_phrases=["living room"], threshold=0.7)
        corrected, changes = fm.correct("the living room is nice")
        # Already correct, should not change
        assert corrected == "the living room is nice"
        assert changes == []


class TestFuzzyMatcherEdgeCases:
    """Edge case tests."""

    def test_empty_text(self) -> None:
        fm = FuzzyMatcher(known_phrases=["客廳燈"], threshold=0.6)
        corrected, changes = fm.correct("")
        assert corrected == ""
        assert changes == []

    def test_no_phrases(self) -> None:
        fm = FuzzyMatcher(known_phrases=[], threshold=0.6)
        corrected, changes = fm.correct("some text")
        assert corrected == "some text"
        assert changes == []

    def test_update_phrases(self) -> None:
        fm = FuzzyMatcher(known_phrases=["客廳燈"], threshold=0.6)
        fm.update_phrases(["臥室燈"])
        corrected, changes = fm.correct("臥室等")
        assert corrected == "臥室燈"
        assert len(changes) == 1

    def test_custom_matcher(self) -> None:
        """A custom PhoneticMatcher can be plugged in."""

        class ReverseMatcher(PhoneticMatcher):
            """Toy matcher: reverses text before comparing."""

            def supports(self, text: str) -> bool:
                return True

            def similarity(self, text_a: str, text_b: str) -> float:
                # Exact reverse match = 1.0, otherwise 0.0
                return 1.0 if text_a[::-1] == text_b else 0.0

            def windows(self, text: str, phrase: str) -> list[tuple[int, int]]:
                plen = len(phrase)
                return [(i, i + plen) for i in range(len(text) - plen + 1)]

        fm = FuzzyMatcher(
            known_phrases=["abc"],
            threshold=0.9,
            matchers=[ReverseMatcher()],
        )
        corrected, changes = fm.correct("xxcbaxx")
        assert corrected == "xxabcxx"
        assert len(changes) == 1
        assert changes[0].confidence == 1.0


class TestFuzzyMatcherExclusions:
    """Tests for exclusion list behavior."""

    def test_excluded_segment_not_corrected(self) -> None:
        """A segment in the exclusion list should not be corrected."""
        fm = FuzzyMatcher(
            known_phrases=["走廊燈"],
            threshold=0.75,
            exclusions=["走廊等"],
        )
        corrected, changes = fm.correct("走廊等")
        assert corrected == "走廊等"
        assert changes == []

    def test_non_excluded_segment_still_corrected(self) -> None:
        """Segments not in exclusion list should still be corrected."""
        fm = FuzzyMatcher(
            known_phrases=["走廊燈", "循環扇"],
            threshold=0.75,
            exclusions=["走廊等"],
        )
        corrected, changes = fm.correct("循環三")
        assert corrected == "循環扇"
        assert len(changes) == 1

    def test_find_candidates_marks_excluded(self) -> None:
        """find_candidates should mark excluded segments."""
        fm = FuzzyMatcher(
            known_phrases=["走廊燈"],
            threshold=0.75,
            exclusions=["走廊等"],
        )
        candidates = fm.find_candidates("走廊等")
        assert len(candidates) >= 1
        match = [c for c in candidates if c.segment == "走廊等"]
        assert len(match) == 1
        assert match[0].excluded is True
        assert match[0].accepted is False

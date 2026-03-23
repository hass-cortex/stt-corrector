"""Tests for Mandarin phonetic matching (languages/mandarin module)."""

from custom_components.stt_corrector.correction.languages.mandarin import (
    pinyin_similarity,
)


class TestPinyinSimilarity:
    """Tests for pinyin_similarity function."""

    def test_identical_strings(self) -> None:
        """Identical strings should have similarity 1.0."""
        assert pinyin_similarity("循環扇", "循環扇") == 1.0

    def test_homophones_high_similarity(self) -> None:
        """Homophones should have high pinyin similarity."""
        # san1 vs shan4 — close pinyin
        ratio = pinyin_similarity("循環三", "循環扇")
        assert ratio >= 0.85

    def test_similar_initial_high_similarity(self) -> None:
        """Characters with similar initials should score high."""
        # lu4 vs ru4 — only initial differs
        ratio = pinyin_similarity("路口燈", "入口燈")
        assert ratio >= 0.85

    def test_tone_only_difference(self) -> None:
        """Characters differing only in tone should score very high."""
        # deng3 vs deng1
        ratio = pinyin_similarity("走廊等", "走廊燈")
        assert ratio >= 0.90

    def test_unrelated_strings_low_similarity(self) -> None:
        """Completely unrelated strings should have low similarity."""
        ratio = pinyin_similarity("天氣", "循環扇")
        assert ratio < 0.5

    def test_different_length_rejected(self) -> None:
        """Strings with very different syllable counts should return 0.0."""
        ratio = pinyin_similarity("燈", "循環扇走廊燈")
        assert ratio == 0.0

    def test_length_difference_one_allowed(self) -> None:
        """Strings differing by one syllable should still be compared."""
        # 2 vs 3 syllables — within the +/- 1 tolerance
        ratio = pinyin_similarity("走廊", "走廊燈")
        assert ratio > 0.0

    def test_empty_string_returns_zero(self) -> None:
        """Empty strings should return 0.0."""
        assert pinyin_similarity("", "循環扇") == 0.0
        assert pinyin_similarity("循環扇", "") == 0.0
        assert pinyin_similarity("", "") == 0.0

    def test_fan_homophones(self) -> None:
        """Common fan-related homophones should match."""
        # 電風三 vs 電風扇
        ratio = pinyin_similarity("電風三", "電風扇")
        assert ratio >= 0.85

    def test_curtain_homophones(self) -> None:
        """Curtain-related homophones should match."""
        # 窗連 vs 窗簾 (lian2 vs lian2 — same pinyin)
        ratio = pinyin_similarity("窗連", "窗簾")
        assert ratio >= 0.90

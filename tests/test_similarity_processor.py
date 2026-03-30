"""Tests for SimilarityProcessor."""

from custom_components.stt_corrector.correction.processors.similarity import (
    SimilarityProcessor,
)
from custom_components.stt_corrector.correction.types import CorrectionMethod


class TestSimilarityProcessor:
    """Tests for fuzzy/phonetic similarity matching processor."""

    def test_fuzzy_match_english(self) -> None:
        sp = SimilarityProcessor(
            known_phrases=["living room"],
            threshold=0.7,
        )
        result, changes = sp.process("turn on livng room light")
        assert "living room" in result
        assert len(changes) == 1
        assert changes[0].method == CorrectionMethod.FUZZY_MATCH

    def test_pinyin_match_chinese(self) -> None:
        sp = SimilarityProcessor(
            known_phrases=["循環扇"],
            threshold=0.75,
        )
        result, changes = sp.process("打開循環三")
        assert result == "打開循環扇"
        assert len(changes) == 1

    def test_no_match_returns_unchanged(self) -> None:
        sp = SimilarityProcessor(
            known_phrases=["kitchen"],
            threshold=0.75,
        )
        result, changes = sp.process("I like chicken")
        assert result == "I like chicken"
        assert changes == []

    def test_empty_text(self) -> None:
        sp = SimilarityProcessor(known_phrases=["hello"], threshold=0.8)
        result, changes = sp.process("")
        assert result == ""
        assert changes == []

    def test_update_phrases(self) -> None:
        sp = SimilarityProcessor(
            known_phrases=["客廳燈"],
            threshold=0.6,
        )
        sp.update_phrases(["臥室燈"])
        result, changes = sp.process("臥室等")
        assert result == "臥室燈"
        assert len(changes) == 1

    def test_find_candidates(self) -> None:
        sp = SimilarityProcessor(
            known_phrases=["循環扇"],
            threshold=0.75,
        )
        sp.process("打開循環三")
        candidates = sp.find_candidates()
        assert len(candidates) > 0
        assert candidates[0].phrase == "循環扇"

    def test_find_candidates_before_process(self) -> None:
        """find_candidates before any process() call should return empty."""
        sp = SimilarityProcessor(known_phrases=["test"], threshold=0.8)
        candidates = sp.find_candidates()
        assert candidates == []

    def test_exclusions(self) -> None:
        sp = SimilarityProcessor(
            known_phrases=["循環扇"],
            threshold=0.75,
            exclusions=["循環三"],
        )
        result, changes = sp.process("打開循環三")
        assert result == "打開循環三"
        assert changes == []

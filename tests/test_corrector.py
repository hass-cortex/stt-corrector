"""Tests for SpeechCorrector pipeline orchestrator."""

from custom_components.stt_corrector.correction.corrector import SpeechCorrector
from custom_components.stt_corrector.correction.languages.mandarin import (
    ChineseScriptConverter,
)
from custom_components.stt_corrector.correction.processors.punctuation import (
    TrailingPunctuationStripper,
)
from custom_components.stt_corrector.correction.processors.replacement import (
    ReplacementProcessor,
)
from custom_components.stt_corrector.correction.processors.similarity import (
    SimilarityProcessor,
)
from custom_components.stt_corrector.correction.types import CorrectionMethod


class TestSpeechCorrectorChinese:
    """Tests for Chinese text correction."""

    def test_custom_replacement(self) -> None:
        sc = SpeechCorrector([ReplacementProcessor({"大門鎖": "大門鎖定"})])
        result = sc.correct("打開大門鎖")
        assert result.corrected == "打開大門鎖定"
        assert len(result.changes) == 1
        assert result.changes[0].method == CorrectionMethod.CUSTOM_RULE

    def test_pinyin_fuzzy_match_homophones(self) -> None:
        sc = SpeechCorrector(
            [
                SimilarityProcessor(known_phrases=["循環扇"], threshold=0.75),
            ]
        )
        result = sc.correct("打開循環三")
        assert result.corrected == "打開循環扇"
        assert len(result.changes) == 1
        assert result.changes[0].method == CorrectionMethod.FUZZY_MATCH

    def test_pinyin_corrects_lamp_homophones(self) -> None:
        sc = SpeechCorrector(
            [
                SimilarityProcessor(known_phrases=["走廊燈"], threshold=0.75),
            ]
        )
        result = sc.correct("打開走廊等")
        assert "走廊燈" in result.corrected

    def test_pinyin_corrects_entrance_homophones(self) -> None:
        sc = SpeechCorrector(
            [
                SimilarityProcessor(known_phrases=["入口燈"], threshold=0.75),
            ]
        )
        result = sc.correct("路口燈")
        assert result.corrected == "入口燈"

    def test_no_change_needed(self) -> None:
        sc = SpeechCorrector(
            [
                SimilarityProcessor(known_phrases=["客廳燈"]),
            ]
        )
        result = sc.correct("打開客廳燈")
        assert result.corrected == "打開客廳燈"
        assert result.changes == []


class TestSpeechCorrectorEnglish:
    """Tests for English text correction."""

    def test_english_custom_replacement(self) -> None:
        sc = SpeechCorrector([ReplacementProcessor({"bed room": "bedroom"})])
        result = sc.correct("turn on bed room light")
        assert result.corrected == "turn on bedroom light"

    def test_english_fuzzy_match(self) -> None:
        sc = SpeechCorrector(
            [
                SimilarityProcessor(known_phrases=["living room"], threshold=0.7),
            ]
        )
        result = sc.correct("turn on livng room light")
        assert "living room" in result.corrected

    def test_english_no_false_positive(self) -> None:
        sc = SpeechCorrector(
            [
                SimilarityProcessor(known_phrases=["kitchen"], threshold=0.75),
            ]
        )
        result = sc.correct("I like chicken")
        assert result.corrected == "I like chicken"


class TestSpeechCorrectorPipeline:
    """Tests for pipeline orchestration."""

    def test_empty_text(self) -> None:
        sc = SpeechCorrector([ReplacementProcessor({"hello": "world"})])
        result = sc.correct("")
        assert result.corrected == ""
        assert result.changes == []

    def test_empty_processors(self) -> None:
        sc = SpeechCorrector([])
        result = sc.correct("hello world")
        assert result.corrected == "hello world"
        assert result.changes == []

    def test_processors_execute_in_order(self) -> None:
        """Script conversion should run before replacements in pipeline order."""
        sc = SpeechCorrector(
            [
                ChineseScriptConverter("s2tw"),
                ReplacementProcessor({"開燈": "開啟電燈"}),
            ]
        )
        result = sc.correct("开灯")
        assert result.corrected == "開啟電燈"
        assert len(result.changes) == 2
        assert result.changes[0].method == CorrectionMethod.SCRIPT_CONVERSION
        assert result.changes[1].method == CorrectionMethod.CUSTOM_RULE

    def test_all_three_processors(self) -> None:
        """All three processors should contribute corrections in order."""
        sc = SpeechCorrector(
            [
                TrailingPunctuationStripper("。"),
                ChineseScriptConverter("s2tw"),
                ReplacementProcessor({"ABC": "XYZ"}),
                SimilarityProcessor(known_phrases=["走廊燈"], threshold=0.75),
            ]
        )
        # After strip: "走廊等和ABC", after s2tw: "走廊等和ABC" (no change),
        # after replacement: "走廊等和XYZ", after similarity: "走廊燈和XYZ"
        result = sc.correct("走廊等和ABC。")
        assert "走廊燈" in result.corrected
        assert "XYZ" in result.corrected
        assert "。" not in result.corrected

    def test_update_phrases_delegates(self) -> None:
        sp = SimilarityProcessor(known_phrases=["客廳燈"], threshold=0.6)
        sc = SpeechCorrector([sp])
        sc.update_phrases(["臥室燈"])
        result = sc.correct("臥室等")
        assert result.corrected == "臥室燈"

    def test_diagnose_includes_all_changes(self) -> None:
        sc = SpeechCorrector(
            [
                ChineseScriptConverter("s2tw"),
                SimilarityProcessor(known_phrases=["開燈"]),
            ]
        )
        diag = sc.diagnose("开灯")
        methods = {c.method for c in diag.changes}
        assert CorrectionMethod.SCRIPT_CONVERSION in methods

    def test_diagnose_includes_candidates(self) -> None:
        sc = SpeechCorrector(
            [
                SimilarityProcessor(known_phrases=["循環扇"], threshold=0.75),
            ]
        )
        diag = sc.diagnose("打開循環三")
        assert len(diag.candidates) > 0

    def test_diagnose_empty_text(self) -> None:
        sc = SpeechCorrector([])
        diag = sc.diagnose("")
        assert diag.corrected == ""
        assert diag.changes == []
        assert diag.candidates == []

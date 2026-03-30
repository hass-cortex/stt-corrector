"""Integration tests for the full correction pipeline.

These tests use REAL processor instances (no mocks on correction logic)
to verify end-to-end pipeline behavior.
"""

from custom_components.stt_corrector.correction.corrector import SpeechCorrector
from custom_components.stt_corrector.correction.languages.mandarin import (
    ChineseScriptConverter,
)
from custom_components.stt_corrector.correction.languages.registry import (
    LanguageModuleRegistry,
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


def _build_corrector_for_locale(
    locale: str | None,
    language_config: dict | None = None,
    custom_replacements: dict[str, str] | None = None,
    known_phrases: list[str] | None = None,
    fuzzy_threshold: float = 0.80,
) -> SpeechCorrector:
    """Build a SpeechCorrector the same way stt.py does."""
    from custom_components.stt_corrector.correction.processors.base import TextProcessor

    processors: list[TextProcessor] = []

    # Language Processing processors
    if locale:
        module = LanguageModuleRegistry.get_module_for_locale(locale)
        if module is not None:
            config = language_config or {}
            module_cfg = config.get(module.module_key(), module.default_config())
            processors.extend(module.get_processors(locale, module_cfg))
    else:
        for module in LanguageModuleRegistry.all_modules():
            config = language_config or {}
            module_cfg = config.get(module.module_key(), module.default_config())
            first_locale = module.locales()[0] if module.locales() else None
            if first_locale:
                processors.extend(module.get_processors(first_locale, module_cfg))

    # Custom Replacements processor
    if custom_replacements:
        processors.append(ReplacementProcessor(custom_replacements))

    # Similarity Matching processor
    matchers = LanguageModuleRegistry.get_matchers(
        locale, language_config=language_config
    )
    processors.append(
        SimilarityProcessor(
            known_phrases=known_phrases or [],
            threshold=fuzzy_threshold,
            matchers=matchers,
        )
    )

    return SpeechCorrector(processors)


class TestFullChinesePipeline:
    """End-to-end tests for Chinese (zh-TW) pipeline."""

    def test_simplified_with_punctuation(self) -> None:
        """Full pipeline: strip punctuation + convert script + similarity match."""
        sc = _build_corrector_for_locale(
            "zh-TW",
            known_phrases=["入口燈"],
            fuzzy_threshold=0.75,
        )
        # Pipeline: "打开入口灯。" -> strip "。" -> s2tw "打開入口燈"
        result = sc.correct("打开入口灯。")
        assert "。" not in result.corrected
        assert "入口燈" in result.corrected
        methods = {c.method for c in result.changes}
        assert CorrectionMethod.PUNCTUATION_STRIP in methods
        assert CorrectionMethod.SCRIPT_CONVERSION in methods

    def test_diagnose_returns_candidates(self) -> None:
        """Diagnose returns fuzzy match candidates with scores."""
        sc = _build_corrector_for_locale(
            "zh-TW",
            known_phrases=["臥室燈"],
            fuzzy_threshold=0.75,
        )
        # Pipeline: "卧室等。" -> strip "。" -> s2tw "臥室等" -> fuzzy "臥室燈"
        # Note: s2tw converts char-by-char (卧->臥), preserving pinyin.
        diag = sc.diagnose("卧室等。")
        assert "臥室燈" in diag.corrected
        assert len(diag.candidates) > 0

    def test_zh_cn_no_script_conversion_by_default(self) -> None:
        """zh-CN defaults: script_conversion off, but strip + pinyin on."""
        sc = _build_corrector_for_locale(
            "zh-CN",
            known_phrases=["循环扇"],
            fuzzy_threshold=0.75,
        )
        result = sc.correct("循环三。")
        assert "。" not in result.corrected
        assert "循环扇" in result.corrected
        # No script_conversion change expected
        methods = {c.method for c in result.changes}
        assert CorrectionMethod.SCRIPT_CONVERSION not in methods


class TestLocaleSwitching:
    """Tests for corrector behavior across locale changes."""

    def test_zh_tw_has_chinese_processors(self) -> None:
        sc = _build_corrector_for_locale("zh-TW")
        # Should have: TrailingPunctuationStripper + ChineseScriptConverter + SimilarityProcessor
        assert len(sc._processors) == 3
        assert isinstance(sc._processors[0], TrailingPunctuationStripper)
        assert isinstance(sc._processors[1], ChineseScriptConverter)
        assert isinstance(sc._processors[2], SimilarityProcessor)

    def test_en_us_has_only_similarity(self) -> None:
        sc = _build_corrector_for_locale("en-US")
        # Should have: SimilarityProcessor only (no language processors for English)
        assert len(sc._processors) == 1
        assert isinstance(sc._processors[0], SimilarityProcessor)

    def test_none_locale_includes_default_processors(self) -> None:
        sc = _build_corrector_for_locale(None)
        # Should have processors from first locale of each module + similarity
        assert len(sc._processors) >= 2

    def test_underscore_locale_matches(self) -> None:
        """zh_TW should produce same processors as zh-TW."""
        sc_hyphen = _build_corrector_for_locale("zh-TW")
        sc_underscore = _build_corrector_for_locale("zh_TW")
        assert len(sc_hyphen._processors) == len(sc_underscore._processors)
        for p1, p2 in zip(
            sc_hyphen._processors, sc_underscore._processors, strict=True
        ):
            assert type(p1) is type(p2)


class TestProcessorToggles:
    """Tests for enabling/disabling individual processors."""

    def test_no_language_processors_when_disabled(self) -> None:
        """When language_processing processor is not added, no language processors."""
        sc = SpeechCorrector(
            [
                ReplacementProcessor({"hello": "world"}),
                SimilarityProcessor(known_phrases=["test"]),
            ]
        )
        result = sc.correct("hello")
        assert result.corrected == "world"

    def test_no_replacements_when_omitted(self) -> None:
        """When ReplacementProcessor is not in list, no replacements."""
        sc = SpeechCorrector(
            [
                SimilarityProcessor(known_phrases=["循環扇"], threshold=0.75),
            ]
        )
        result = sc.correct("循環三和ABC")
        assert "ABC" in result.corrected  # Not replaced
        assert "循環扇" in result.corrected  # But similarity works

    def test_no_similarity_when_omitted(self) -> None:
        """When SimilarityProcessor is not in list, no fuzzy matching."""
        sc = SpeechCorrector(
            [
                ReplacementProcessor({"ABC": "XYZ"}),
            ]
        )
        result = sc.correct("循環三和ABC")
        assert "XYZ" in result.corrected
        assert "循環三" in result.corrected  # Not fuzzy matched


class TestReplacementBeforeSimilarity:
    """Verify replacement runs before similarity in the pipeline."""

    def test_replacement_output_feeds_similarity(self) -> None:
        """Replacements modify text, then similarity matches the modified text."""
        sc = SpeechCorrector(
            [
                ReplacementProcessor({"wrong_name": "循環扇"}),
                SimilarityProcessor(known_phrases=["循環扇"], threshold=0.75),
            ]
        )
        result = sc.correct("打開wrong_name")
        assert "循環扇" in result.corrected
        assert any(c.method == CorrectionMethod.CUSTOM_RULE for c in result.changes)


class TestPhraseUpdates:
    """Tests for runtime phrase updates through the pipeline."""

    def test_update_phrases_reaches_similarity_processor(self) -> None:
        sp = SimilarityProcessor(known_phrases=[], threshold=0.6)
        sc = SpeechCorrector(
            [
                TrailingPunctuationStripper("。"),
                sp,
            ]
        )
        # Initially no phrases — no correction
        result = sc.correct("臥室等。")
        assert "臥室等" in result.corrected

        # Update phrases — now should correct
        sc.update_phrases(["臥室燈"])
        result = sc.correct("臥室等。")
        assert "臥室燈" in result.corrected

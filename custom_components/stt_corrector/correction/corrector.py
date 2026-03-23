"""Two-stage STT text correction pipeline."""

from __future__ import annotations

from .fuzzy_matcher import FuzzyMatcher
from .matchers import PhoneticMatcher
from .types import (
    CorrectionChange,
    CorrectionMethod,
    CorrectionResult,
    DiagnosticResult,
)


class SpeechCorrector:
    """Two-stage text correction pipeline for STT output.

    Pipeline stages (executed in order):
    1. Custom replacements - user-defined string substitutions
    2. Fuzzy/Pinyin matching - pinyin for Chinese, SequenceMatcher for others
    """

    def __init__(
        self,
        known_phrases: list[str] | None = None,
        custom_replacements: dict[str, str] | None = None,
        fuzzy_threshold: float = 0.80,
        enable_custom_replacements: bool = True,
        enable_fuzzy_matching: bool = True,
        matchers: list[PhoneticMatcher] | None = None,
        exclusions: list[str] | None = None,
    ) -> None:
        """Initialize the two-stage corrector.

        Args:
            known_phrases: Correct phrases for fuzzy/pinyin matching.
            custom_replacements: Custom string replacement rules.
            fuzzy_threshold: Minimum similarity for fuzzy matching (0.0-1.0).
            enable_custom_replacements: Toggle custom replacement stage.
            enable_fuzzy_matching: Toggle fuzzy/pinyin matching stage.
            matchers: Ordered list of phonetic matchers for fuzzy matching.
                      Defaults to all registered matchers when not provided.
            exclusions: Segments to never correct via fuzzy matching.
        """
        # Stage flags
        self._enable_custom_replacements = enable_custom_replacements
        self._enable_fuzzy_matching = enable_fuzzy_matching

        # Stage 1: Custom replacements (pre-sorted by key length descending)
        raw = custom_replacements or {}
        self._sorted_rules: list[tuple[str, str]] = sorted(
            raw.items(), key=lambda item: len(item[0]), reverse=True
        )

        # Stage 2: Fuzzy matching with pluggable phonetic matchers
        self._fuzzy = FuzzyMatcher(
            known_phrases=known_phrases or [],
            threshold=fuzzy_threshold,
            matchers=matchers,
            exclusions=exclusions,
        )

    def correct(self, text: str) -> CorrectionResult:
        """Run the two-stage correction pipeline.

        Args:
            text: Input text to correct.

        Returns:
            CorrectionResult with original text, corrected text, and changes.
        """
        if not text:
            return CorrectionResult(original=text, corrected=text)

        corrected, _, changes = self._run_pipeline(text)
        return CorrectionResult(original=text, corrected=corrected, changes=changes)

    def diagnose(self, text: str) -> DiagnosticResult:
        """Run correction pipeline with diagnostic candidate info.

        Returns the same correction result plus all fuzzy match
        candidates and their scores. Candidates are computed against
        the post-custom-replacement text (what the fuzzy matcher sees).
        """
        if not text:
            return DiagnosticResult(original=text, corrected=text)

        corrected, post_replacement, changes = self._run_pipeline(text)

        # Candidates computed against post-replacement text
        candidates = (
            self._fuzzy.find_candidates(post_replacement)
            if self._enable_fuzzy_matching
            else []
        )

        return DiagnosticResult(
            original=text,
            corrected=corrected,
            changes=changes,
            candidates=candidates,
        )

    def _run_pipeline(self, text: str) -> tuple[str, str, list[CorrectionChange]]:
        """Run the two-stage pipeline and return results.

        Returns:
            Tuple of (final_text, post_replacement_text, changes).
        """
        all_changes: list[CorrectionChange] = []
        current = text

        # Stage 1: Custom replacements
        if self._enable_custom_replacements:
            current, custom_changes = self._apply_custom_replacements(current)
            all_changes.extend(custom_changes)

        post_replacement = current

        # Stage 2: Fuzzy/Pinyin matching
        if self._enable_fuzzy_matching:
            current, fuzzy_changes = self._fuzzy.correct(current)
            all_changes.extend(fuzzy_changes)

        return current, post_replacement, all_changes

    def update_phrases(self, phrases: list[str]) -> None:
        """Update the fuzzy matcher's known phrases.

        Args:
            phrases: New list of correct phrases.
        """
        self._fuzzy.update_phrases(phrases)

    def _apply_custom_replacements(
        self, text: str
    ) -> tuple[str, list[CorrectionChange]]:
        """Apply custom string replacements.

        Rules are sorted by key length descending to prevent partial matches.

        Args:
            text: Text to apply replacements to.

        Returns:
            Tuple of (corrected_text, list_of_changes).
        """
        if not self._sorted_rules:
            return text, []

        changes: list[CorrectionChange] = []
        corrected = text

        for old, new in self._sorted_rules:
            if old in corrected:
                corrected = corrected.replace(old, new)
                changes.append(
                    CorrectionChange(
                        original_segment=old,
                        corrected_segment=new,
                        method=CorrectionMethod.CUSTOM_RULE,
                        confidence=1.0,
                    )
                )

        return corrected, changes

"""Fuzzy/phonetic similarity matching processor for the correction pipeline."""

from __future__ import annotations

from ..fuzzy_matcher import FuzzyMatcher
from ..matchers import PhoneticMatcher
from ..types import CorrectionCandidate, CorrectionChange
from .base import TextProcessor


class SimilarityProcessor(TextProcessor):
    """Apply fuzzy/phonetic similarity matching against known phrases.

    Wraps FuzzyMatcher as a TextProcessor for uniform pipeline iteration.
    Provides additional methods for phrase updates and diagnostic candidates.
    """

    def __init__(
        self,
        known_phrases: list[str] | None = None,
        threshold: float = 0.80,
        matchers: list[PhoneticMatcher] | None = None,
        exclusions: list[str] | None = None,
    ) -> None:
        """Initialize similarity processor.

        Args:
            known_phrases: Correct phrases to match against.
            threshold: Minimum similarity ratio to accept a match (0.0-1.0).
            matchers: Ordered list of phonetic matchers. First match wins.
            exclusions: Segments to never correct.
        """
        self._fuzzy = FuzzyMatcher(
            known_phrases=known_phrases or [],
            threshold=threshold,
            matchers=matchers,
            exclusions=exclusions,
        )

    def process(self, text: str) -> tuple[str, list[CorrectionChange]]:
        """Apply fuzzy matching corrections to text.

        Args:
            text: Input text to correct.

        Returns:
            Tuple of (corrected_text, list_of_changes).
        """
        # Delegate empty text to correct() too: it returns (text, []) and resets the candidate
        # cache, so an empty turn after a non-empty one doesn't leave stale diagnostic candidates.
        return self._fuzzy.correct(text)

    def update_phrases(self, phrases: list[str]) -> None:
        """Update the known phrases list.

        Args:
            phrases: New list of correct phrases.
        """
        self._fuzzy.update_phrases(phrases)

    def find_candidates(self, min_score: float = 0.5) -> list[CorrectionCandidate]:
        """Return the candidates captured during the last process() call.

        Empty before any process() call.

        Args:
            min_score: Minimum similarity score to include.

        Returns:
            List of CorrectionCandidate sorted by score descending.
        """
        return self._fuzzy.last_candidates(min_score)

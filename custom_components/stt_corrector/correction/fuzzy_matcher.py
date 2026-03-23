"""Fuzzy matching for STT text correction using pluggable phonetic matchers.

Uses an extensible matcher architecture where each language family provides
its own phonetic comparison and sliding window strategy. See matchers.py
for the PhoneticMatcher base class and built-in implementations.
"""

from __future__ import annotations

from .matchers import PhoneticMatcher
from .types import CorrectionCandidate, CorrectionChange, CorrectionMethod

# Minimum phrase length to consider for matching
_MIN_PHRASE_LEN = 2


class FuzzyMatcher:
    """Fuzzy text matcher with pluggable phonetic matchers.

    Tries matchers in order and uses the first one that supports the input
    text. When no matchers are provided, defaults to all registered matchers.
    """

    def __init__(
        self,
        known_phrases: list[str],
        threshold: float = 0.80,
        matchers: list[PhoneticMatcher] | None = None,
        exclusions: list[str] | None = None,
    ) -> None:
        """Initialize the fuzzy matcher.

        Args:
            known_phrases: List of correct phrases to match against.
            threshold: Minimum similarity ratio to accept a match (0.0-1.0).
            matchers: Ordered list of phonetic matchers. First match wins.
                      Defaults to all registered matchers when not provided.
            exclusions: Segments to never correct (skip fuzzy matching).
        """
        if matchers is None:
            from .registry import MatcherRegistry

            matchers = MatcherRegistry.get_matchers(None)
        self._threshold = threshold
        self._phrases: list[str] = []
        self._set_phrases(known_phrases)
        self._matchers = matchers
        self._exclusions: set[str] = set(exclusions or [])

    def _set_phrases(self, phrases: list[str]) -> None:
        """Set and sort phrases by length descending, filtering short ones."""
        self._phrases = sorted(
            [p for p in phrases if len(p) >= _MIN_PHRASE_LEN],
            key=len,
            reverse=True,
        )

    def _get_matcher(self, text: str) -> PhoneticMatcher:
        """Find the first matcher that supports the given text."""
        for matcher in self._matchers:
            if matcher.supports(text):
                return matcher
        return self._matchers[-1]

    def update_phrases(self, phrases: list[str]) -> None:
        """Update the known phrases list.

        Args:
            phrases: New list of correct phrases.
        """
        self._set_phrases(phrases)

    def correct(self, text: str) -> tuple[str, list[CorrectionChange]]:
        """Apply fuzzy matching corrections to the given text.

        Args:
            text: Input text to correct.

        Returns:
            Tuple of (corrected_text, list_of_changes).
        """
        if not text or not self._phrases:
            return text, []

        changes: list[CorrectionChange] = []
        corrected = text

        # Build protected regions: positions of known phrases already in text.
        # This prevents fuzzy matching from corrupting substrings that are
        # part of a correctly recognized longer phrase (e.g., "口燈" inside "入口燈").
        protected: list[tuple[int, int]] = []
        for phrase in self._phrases:
            start = 0
            while True:
                idx = corrected.find(phrase, start)
                if idx == -1:
                    break
                protected.append((idx, idx + len(phrase)))
                start = idx + 1

        for phrase in self._phrases:
            # Skip if phrase already exists exactly in the text
            if phrase in corrected:
                continue

            best_match = self._find_best_match(corrected, phrase)
            if best_match is not None:
                start, end, ratio = best_match
                segment = corrected[start:end]

                # Skip if segment is in exclusion list
                if segment in self._exclusions:
                    continue

                # Skip if the match overlaps with a protected region
                if any(start < p_end and end > p_start for p_start, p_end in protected):
                    continue

                if segment != phrase:
                    # Update protected regions to account for length change.
                    # Safe because the overlap check above guarantees the replaced
                    # segment does not overlap any protected region, so only regions
                    # after the replacement point need shifting.
                    len_diff = len(phrase) - len(segment)
                    protected = [
                        (p_start + len_diff, p_end + len_diff)
                        if p_start >= end
                        else (p_start, p_end)
                        for p_start, p_end in protected
                    ]
                    corrected = corrected[:start] + phrase + corrected[end:]
                    # Add the newly corrected region as protected
                    protected.append((start, start + len(phrase)))
                    changes.append(
                        CorrectionChange(
                            original_segment=segment,
                            corrected_segment=phrase,
                            method=CorrectionMethod.FUZZY_MATCH,
                            confidence=ratio,
                        )
                    )

        return corrected, changes

    def find_candidates(
        self, text: str, min_score: float = 0.5
    ) -> list[CorrectionCandidate]:
        """Find all candidate matches with scores for diagnostic purposes.

        Args:
            text: Input text to analyze.
            min_score: Minimum similarity score to include in results.

        Returns:
            List of CorrectionCandidate sorted by score descending.
        """
        if not text or not self._phrases:
            return []

        candidates: list[CorrectionCandidate] = []
        seen: set[tuple[str, str]] = set()

        for phrase in self._phrases:
            if phrase in text:
                continue

            best = self._find_best_candidate(text, phrase, min_score)
            if best is not None:
                start, end, ratio = best
                segment = text[start:end]
                key = (segment, phrase)
                if key not in seen:
                    seen.add(key)
                    is_excluded = segment in self._exclusions
                    candidates.append(
                        CorrectionCandidate(
                            phrase=phrase,
                            segment=segment,
                            score=round(ratio, 4),
                            threshold=self._threshold,
                            accepted=ratio >= self._threshold and not is_excluded,
                            excluded=is_excluded,
                        )
                    )

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def _find_best(
        self, text: str, phrase: str, threshold: float
    ) -> tuple[int, int, float] | None:
        """Find the best match for a phrase using a sliding window approach.

        Selects the appropriate phonetic matcher based on the phrase content,
        then uses that matcher's window strategy and similarity function.

        Args:
            text: Text to search in.
            phrase: Phrase to match.
            threshold: Minimum similarity ratio to accept a match (0.0-1.0).

        Returns:
            Tuple of (start, end, ratio) or None if no match above threshold.
        """
        matcher = self._get_matcher(phrase)
        windows = matcher.windows(text, phrase)

        phrase_len = len(phrase)
        best: tuple[float, float, int, int] | None = None

        for start, end in windows:
            candidate = text[start:end]
            ratio = matcher.similarity(candidate, phrase)

            if ratio >= threshold:
                length_ratio = min(len(candidate), phrase_len) / max(
                    len(candidate), phrase_len
                )
                score = ratio * length_ratio
                if best is None or score > best[0]:
                    best = (score, ratio, start, end)

        if best is None:
            return None
        return (best[2], best[3], best[1])

    def _find_best_match(self, text: str, phrase: str) -> tuple[int, int, float] | None:
        """Find the best fuzzy match above the configured threshold."""
        return self._find_best(text, phrase, self._threshold)

    def _find_best_candidate(
        self, text: str, phrase: str, min_score: float
    ) -> tuple[int, int, float] | None:
        """Find the best match for a phrase with a custom minimum score."""
        return self._find_best(text, phrase, min_score)

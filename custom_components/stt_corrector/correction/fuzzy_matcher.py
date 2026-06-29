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

# Floor for retaining diagnostic candidates (near-misses below the accept threshold), so the
# test service / DEBUG logging can show why a correction was or wasn't applied.
_CANDIDATE_FLOOR = 0.5


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
            from .languages.registry import LanguageModuleRegistry

            matchers = LanguageModuleRegistry.get_matchers(None)
        self._threshold = threshold
        self._phrases: list[str] = []
        self._set_phrases(known_phrases)
        self._matchers = matchers
        self._exclusions: set[str] = set(exclusions or [])
        # Raw (phrase, segment, ratio) candidates from the last correct() scan; materialized on
        # demand by last_candidates().
        self._last_candidate_raw: list[tuple[str, str, float]] = []

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
        """Apply fuzzy matching corrections, capturing diagnostic candidates in the same scan.

        Each phrase's sliding-window similarity is computed once; from it both the applied
        correction (best window >= threshold) and the diagnostic candidate (best window >= the
        candidate floor) are derived. last_candidates() returns the captured candidates.

        Args:
            text: Input text to correct.

        Returns:
            Tuple of (corrected_text, list_of_changes).
        """
        self._last_candidate_raw = []
        if not text or not self._phrases:
            return text, []

        changes: list[CorrectionChange] = []
        corrected = text
        cand_raw: list[tuple[str, str, float]] = []

        # Build protected regions: positions of known phrases already in text. This prevents fuzzy
        # matching from corrupting substrings that are part of a correctly recognized longer phrase
        # (e.g., "口燈" inside "入口燈").
        protected: list[tuple[int, int]] = []
        for phrase in self._phrases:
            start = 0
            while True:
                idx = corrected.find(phrase, start)
                if idx == -1:
                    break
                protected.append((idx, idx + len(phrase)))
                start = idx + 1

        floor = min(_CANDIDATE_FLOOR, self._threshold)
        for phrase in self._phrases:
            # Skip if phrase already exists exactly in the text
            if phrase in corrected:
                continue

            best_match, best_cand = self._scan_phrase(corrected, phrase, floor)

            # Record the diagnostic candidate (best near-match >= floor) regardless of acceptance.
            if best_cand is not None:
                c_start, c_end, c_ratio = best_cand
                cand_raw.append((phrase, corrected[c_start:c_end], c_ratio))

            if best_match is None:
                continue
            start, end, ratio = best_match
            segment = corrected[start:end]

            # Skip if segment is in exclusion list
            if segment in self._exclusions:
                continue

            # Skip if the match overlaps with a protected region
            if any(start < p_end and end > p_start for p_start, p_end in protected):
                continue

            if segment != phrase:
                # Update protected regions to account for length change. Safe because the overlap
                # check above guarantees the replaced segment does not overlap any protected region,
                # so only regions after the replacement point need shifting.
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

        self._last_candidate_raw = cand_raw
        return corrected, changes

    def last_candidates(
        self, min_score: float = _CANDIDATE_FLOOR
    ) -> list[CorrectionCandidate]:
        """Return the diagnostic candidates captured during the last correct() — no re-scan.

        Args:
            min_score: Minimum similarity score to include.

        Returns:
            List of CorrectionCandidate sorted by score descending.
        """
        return self._build_candidates(self._last_candidate_raw, min_score)

    def find_candidates(
        self, text: str, min_score: float = _CANDIDATE_FLOOR
    ) -> list[CorrectionCandidate]:
        """Scan ``text`` standalone and return all candidate matches with scores.

        For a transcript already run through correct(), prefer {@link last_candidates}. This
        standalone scan is for callers that have not run correct() on ``text``.

        Args:
            text: Input text to analyze.
            min_score: Minimum similarity score to include.

        Returns:
            List of CorrectionCandidate sorted by score descending.
        """
        if not text or not self._phrases:
            return []

        cand_raw: list[tuple[str, str, float]] = []
        for phrase in self._phrases:
            if phrase in text:
                continue
            _, best_cand = self._scan_phrase(text, phrase, min_score)
            if best_cand is not None:
                start, end, ratio = best_cand
                cand_raw.append((phrase, text[start:end], ratio))
        return self._build_candidates(cand_raw, min_score)

    def _build_candidates(
        self, cand_raw: list[tuple[str, str, float]], min_score: float
    ) -> list[CorrectionCandidate]:
        """Materialize raw (phrase, segment, ratio) tuples into sorted CorrectionCandidates."""
        candidates: list[CorrectionCandidate] = []
        seen: set[tuple[str, str]] = set()
        for phrase, segment, ratio in cand_raw:
            if ratio < min_score:
                continue
            key = (segment, phrase)
            if key in seen:
                continue
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

    def _scan_phrase(
        self, text: str, phrase: str, floor: float
    ) -> tuple[tuple[int, int, float] | None, tuple[int, int, float] | None]:
        """Scan a phrase against text once, deriving both the correction match and the candidate.

        Computes each sliding-window similarity once and tracks two best-by-score windows: the
        correction match (ratio >= threshold) and the diagnostic candidate (ratio >= ``floor``).

        Args:
            text: Text to search in.
            phrase: Phrase to match.
            floor: Minimum ratio for a window to be retained as a candidate (<= threshold so the
                correction match is never missed).

        Returns:
            Tuple of (best_match, best_candidate), each (start, end, ratio) or None.
        """
        matcher = self._get_matcher(phrase)
        windows = matcher.windows(text, phrase)
        phrase_len = len(phrase)

        best_match: tuple[float, float, int, int] | None = None
        best_cand: tuple[float, float, int, int] | None = None
        for start, end in windows:
            candidate = text[start:end]
            ratio = matcher.similarity(candidate, phrase)
            if ratio < floor:
                continue
            length_ratio = min(len(candidate), phrase_len) / max(
                len(candidate), phrase_len
            )
            score = ratio * length_ratio
            if best_cand is None or score > best_cand[0]:
                best_cand = (score, ratio, start, end)
            if ratio >= self._threshold and (
                best_match is None or score > best_match[0]
            ):
                best_match = (score, ratio, start, end)

        bm = (best_match[2], best_match[3], best_match[1]) if best_match else None
        bc = (best_cand[2], best_cand[3], best_cand[1]) if best_cand else None
        return bm, bc

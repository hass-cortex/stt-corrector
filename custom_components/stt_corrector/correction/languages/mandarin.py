"""Chinese (Mandarin) phonetic matching for STT text correction.

Combines CJK character detection with pinyin-based syllable-level comparison.
Uses tone separation and similar-initial boosting for acoustically similar
Mandarin syllables, instead of flat string comparison via SequenceMatcher.
"""

from __future__ import annotations

import re
from itertools import zip_longest

from pypinyin import Style, lazy_pinyin

from ..matchers import PhoneticMatcher

# ---------------------------------------------------------------------------
# Pinyin similarity helpers
# ---------------------------------------------------------------------------

# Regex to split a TONE3 pinyin syllable into base + tone number
_TONE_RE = re.compile(r"^(.+?)(\d)?$")

# Groups of acoustically similar initials in Mandarin.
# Within each group, confusion is common in STT output.
_SIMILAR_INITIALS: list[set[str]] = [
    {"l", "r", "n"},
    {"zh", "z"},
    {"ch", "c"},
    {"sh", "s"},
    {"f", "h"},
]

# Known initial consonants (longest first for greedy match)
_INITIALS = [
    "zh",
    "ch",
    "sh",
    "b",
    "p",
    "m",
    "f",
    "d",
    "t",
    "n",
    "l",
    "g",
    "k",
    "h",
    "j",
    "q",
    "x",
    "z",
    "c",
    "s",
    "r",
    "y",
    "w",
]


def _split_tone(syllable: str) -> tuple[str, str]:
    """Split a TONE3 pinyin syllable into (base, tone).

    Example: "deng1" -> ("deng", "1"), "a" -> ("a", "")
    """
    m = _TONE_RE.match(syllable)
    if m:
        return m.group(1), m.group(2) or ""
    return syllable, ""


def _get_initial(base: str) -> str:
    """Extract the initial consonant from a pinyin base.

    Example: "deng" -> "d", "zhi" -> "zh", "an" -> ""
    """
    for initial in _INITIALS:
        if base.startswith(initial):
            return initial
    return ""


def _are_similar_initials(a: str, b: str) -> bool:
    """Check if two initials belong to the same confusion group."""
    for group in _SIMILAR_INITIALS:
        if a in group and b in group:
            return True
    return False


def _syllable_similarity(syl_a: str, syl_b: str) -> float:
    """Compare two pinyin syllables with phonetic awareness.

    Scoring:
    - Base match (without tone): 0.85 base score
    - Tone match bonus: +0.15 (total 1.0 for perfect match)
    - Similar initial with same final: 0.7
    - Partial base overlap: scaled by character overlap ratio
    """
    base_a, tone_a = _split_tone(syl_a)
    base_b, tone_b = _split_tone(syl_b)

    tone_bonus = 0.15 if tone_a == tone_b else 0.0

    # Exact base match
    if base_a == base_b:
        return 0.85 + tone_bonus

    # Similar initial with same final
    init_a = _get_initial(base_a)
    init_b = _get_initial(base_b)
    final_a = base_a[len(init_a) :]
    final_b = base_b[len(init_b) :]

    if final_a and final_a == final_b and _are_similar_initials(init_a, init_b):
        return 0.70 + tone_bonus

    # Same initial, different final — partial credit
    if init_a and init_a == init_b:
        # Score based on final overlap
        max_len = max(len(final_a), len(final_b), 1)
        common = sum(a == b for a, b in zip(final_a, final_b))
        return 0.3 + 0.3 * (common / max_len) + tone_bonus

    return 0.0


def pinyin_similarity(text_a: str, text_b: str) -> float:
    """Compare two Chinese strings by syllable-level pinyin similarity.

    Converts both strings to pinyin, then compares syllable by syllable
    with phonetic awareness (tone separation, similar-initial boosting).

    Args:
        text_a: First Chinese string.
        text_b: Second Chinese string.

    Returns:
        Similarity ratio between 0.0 and 1.0.
    """
    pinyin_a = lazy_pinyin(text_a, style=Style.TONE3)
    pinyin_b = lazy_pinyin(text_b, style=Style.TONE3)

    if not pinyin_a or not pinyin_b:
        return 0.0

    # Different syllable count = likely not the same phrase.
    # Allow +/- 1 difference for slight misrecognition.
    if abs(len(pinyin_a) - len(pinyin_b)) > 1:
        return 0.0

    # Compare each syllable pair, padding the shorter list with empty strings
    max_len = max(len(pinyin_a), len(pinyin_b))
    total = 0.0
    for syl_a, syl_b in zip_longest(pinyin_a, pinyin_b, fillvalue=""):
        total += _syllable_similarity(syl_a, syl_b)

    return total / max_len


# ---------------------------------------------------------------------------
# PinyinMatcher — PhoneticMatcher subclass for CJK text
# ---------------------------------------------------------------------------

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


class PinyinMatcher(PhoneticMatcher):
    """Chinese phonetic matching using pypinyin.

    Handles CJK text with character-level sliding windows and
    pinyin-based similarity comparison. Only activates for text
    containing CJK characters.

    Note: Locale-based matcher selection at the entity level controls
    whether PinyinMatcher is included at all. The supports() check
    provides a second guard for mixed-language text.
    """

    def supports(self, text: str) -> bool:
        return bool(_CJK_RE.search(text))

    def similarity(self, text_a: str, text_b: str) -> float:
        return pinyin_similarity(text_a, text_b)

    def windows(self, text: str, phrase: str) -> list[tuple[int, int]]:
        phrase_len = len(phrase)
        result: list[tuple[int, int]] = []
        for window_size in range(max(1, phrase_len - 1), phrase_len + 2):
            for start in range(max(0, len(text) - window_size + 1)):
                end = start + window_size
                if end <= len(text):
                    result.append((start, end))
        return result

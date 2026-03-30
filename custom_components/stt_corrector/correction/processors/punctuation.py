"""Trailing punctuation stripping processor for STT output."""

from __future__ import annotations

from ..types import CorrectionChange, CorrectionMethod
from .base import TextProcessor


class TrailingPunctuationStripper(TextProcessor):
    """Strip trailing punctuation characters from STT output.

    Many STT engines append sentence-ending punctuation (e.g., "。", "？")
    that is meaningless for voice commands and can interfere with downstream
    correction processors.

    Args:
        punctuation: String of characters to strip from the end of text.
    """

    def __init__(self, punctuation: str) -> None:
        self._punctuation = punctuation

    def process(self, text: str) -> tuple[str, list[CorrectionChange]]:
        """Strip trailing punctuation from text.

        Args:
            text: Input text to process.

        Returns:
            Tuple of (stripped_text, list_of_changes).
        """
        if not text or not self._punctuation:
            return text, []

        stripped = text.rstrip(self._punctuation)
        if stripped == text:
            return text, []

        return stripped, [
            CorrectionChange(
                original_segment=text,
                corrected_segment=stripped,
                method=CorrectionMethod.PUNCTUATION_STRIP,
                confidence=1.0,
            )
        ]

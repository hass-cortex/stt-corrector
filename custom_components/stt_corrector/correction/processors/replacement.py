"""Custom text replacement processor for the correction pipeline."""

from __future__ import annotations

from ..types import CorrectionChange, CorrectionMethod
from .base import TextProcessor


class ReplacementProcessor(TextProcessor):
    """Apply user-defined exact-match text substitutions.

    Rules are sorted by key length descending to prevent partial matches
    from interfering with longer replacement keys.
    """

    def __init__(self, rules: dict[str, str]) -> None:
        """Initialize with replacement rules.

        Args:
            rules: Dictionary mapping wrong text to correct text.
        """
        self._sorted_rules: list[tuple[str, str]] = sorted(
            rules.items(), key=lambda item: len(item[0]), reverse=True
        )

    def process(self, text: str) -> tuple[str, list[CorrectionChange]]:
        """Apply replacement rules to text.

        Args:
            text: Input text to process.

        Returns:
            Tuple of (corrected_text, list_of_changes).
        """
        if not text or not self._sorted_rules:
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

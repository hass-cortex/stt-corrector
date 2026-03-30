"""Base class for text processors in the correction pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import CorrectionCandidate, CorrectionChange


class TextProcessor(ABC):
    """Base class for all correction pipeline processors.

    Each processor transforms text and returns the result with a list
    of changes. Processors are executed in order by SpeechCorrector.

    Subclasses may override update_phrases() and find_candidates()
    to support runtime phrase updates and diagnostic output.
    """

    @abstractmethod
    def process(self, text: str) -> tuple[str, list[CorrectionChange]]:
        """Process text and return result with changes.

        Args:
            text: Input text to process.

        Returns:
            Tuple of (processed_text, list_of_changes).
        """

    def update_phrases(self, phrases: list[str]) -> None:  # noqa: B027
        """Update known phrases. Override in subclasses that use phrases."""

    def find_candidates(self, min_score: float = 0.5) -> list[CorrectionCandidate]:
        """Return diagnostic candidates. Override in subclasses that support it."""
        return []

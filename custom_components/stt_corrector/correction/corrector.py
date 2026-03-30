"""Text correction pipeline orchestrator."""

from __future__ import annotations

from .processors.base import TextProcessor
from .types import (
    CorrectionCandidate,
    CorrectionChange,
    CorrectionResult,
    DiagnosticResult,
)


class SpeechCorrector:
    """Orchestrates a pipeline of TextProcessor instances.

    Executes processors in order. Each processor transforms text and
    reports changes. The pipeline is fully data-driven — all processor
    configuration is handled by the builder that constructs the
    processor list.
    """

    def __init__(self, processors: list[TextProcessor]) -> None:
        """Initialize with an ordered list of processors.

        Args:
            processors: Ordered list of TextProcessor instances to execute.
        """
        self._processors = processors

    def correct(self, text: str) -> CorrectionResult:
        """Run the correction pipeline.

        Args:
            text: Input text to correct.

        Returns:
            CorrectionResult with original text, corrected text, and changes.
        """
        if not text:
            return CorrectionResult(original=text, corrected=text)

        corrected, changes = self._run_pipeline(text)
        return CorrectionResult(original=text, corrected=corrected, changes=changes)

    def diagnose(self, text: str) -> DiagnosticResult:
        """Run pipeline with diagnostic candidate info.

        Returns the correction result plus all fuzzy match candidates
        and their scores from any SimilarityProcessor in the pipeline.
        """
        if not text:
            return DiagnosticResult(original=text, corrected=text)

        corrected, changes = self._run_pipeline(text)

        candidates: list[CorrectionCandidate] = []
        for processor in self._processors:
            found = processor.find_candidates()
            if found:
                candidates = found
                break

        return DiagnosticResult(
            original=text,
            corrected=corrected,
            changes=changes,
            candidates=candidates,
        )

    def update_phrases(self, phrases: list[str]) -> None:
        """Update known phrases on all processors that support it.

        Args:
            phrases: New list of correct phrases.
        """
        for processor in self._processors:
            processor.update_phrases(phrases)

    def _run_pipeline(self, text: str) -> tuple[str, list[CorrectionChange]]:
        """Execute all processors in order.

        Returns:
            Tuple of (final_text, all_changes).
        """
        all_changes: list[CorrectionChange] = []
        current = text

        for processor in self._processors:
            current, changes = processor.process(current)
            all_changes.extend(changes)

        return current, all_changes

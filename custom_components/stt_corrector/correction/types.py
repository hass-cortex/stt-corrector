"""Data types for STT correction results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CorrectionMethod(StrEnum):
    """Method used to apply a correction."""

    CUSTOM_RULE = "custom_rule"
    FUZZY_MATCH = "fuzzy_match"


@dataclass(slots=True)
class CorrectionChange:
    """A single correction applied to the text."""

    original_segment: str
    corrected_segment: str
    method: CorrectionMethod
    confidence: float  # 1.0 for exact matches, <1.0 for fuzzy


@dataclass(slots=True)
class CorrectionCandidate:
    """A candidate match considered during fuzzy matching."""

    phrase: str
    segment: str
    score: float
    threshold: float
    accepted: bool
    excluded: bool = False


@dataclass(slots=True)
class CorrectionResult:
    """Result of text correction."""

    original: str
    corrected: str
    changes: list[CorrectionChange] = field(default_factory=list)


@dataclass(slots=True)
class DiagnosticResult:
    """Result of diagnostic correction with candidate details."""

    original: str
    corrected: str
    changes: list[CorrectionChange] = field(default_factory=list)
    candidates: list[CorrectionCandidate] = field(default_factory=list)

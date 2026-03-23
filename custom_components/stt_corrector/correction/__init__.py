"""STT post-recognition text correction library."""

from .corrector import SpeechCorrector
from .fuzzy_matcher import FuzzyMatcher
from .languages.mandarin import PinyinMatcher
from .matchers import DefaultMatcher, PhoneticMatcher
from .registry import MatcherRegistry
from .types import (
    CorrectionCandidate,
    CorrectionChange,
    CorrectionMethod,
    CorrectionResult,
    DiagnosticResult,
)

__all__ = [
    "CorrectionCandidate",
    "CorrectionChange",
    "CorrectionMethod",
    "CorrectionResult",
    "DiagnosticResult",
    "DefaultMatcher",
    "FuzzyMatcher",
    "MatcherRegistry",
    "PhoneticMatcher",
    "PinyinMatcher",
    "SpeechCorrector",
]

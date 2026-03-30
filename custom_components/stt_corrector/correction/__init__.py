"""STT post-recognition text correction library."""

# Consumer API
from .corrector import SpeechCorrector

# Implementations
from .fuzzy_matcher import FuzzyMatcher

# Framework API
from .languages import LanguageModule
from .languages.mandarin import PinyinMatcher
from .languages.registry import LanguageModuleRegistry
from .matchers import DefaultMatcher, PhoneticMatcher
from .processors import (
    ReplacementProcessor,
    SimilarityProcessor,
    TextProcessor,
    TrailingPunctuationStripper,
)
from .types import (
    CorrectionCandidate,
    CorrectionChange,
    CorrectionMethod,
    CorrectionResult,
    DiagnosticResult,
)

__all__ = [
    # Consumer API
    "SpeechCorrector",
    "CorrectionCandidate",
    "CorrectionChange",
    "CorrectionMethod",
    "CorrectionResult",
    "DiagnosticResult",
    # Framework API
    "LanguageModule",
    "LanguageModuleRegistry",
    "TextProcessor",
    "PhoneticMatcher",
    # Processors
    "ReplacementProcessor",
    "SimilarityProcessor",
    "TrailingPunctuationStripper",
    # Implementations
    "DefaultMatcher",
    "FuzzyMatcher",
    "PinyinMatcher",
]

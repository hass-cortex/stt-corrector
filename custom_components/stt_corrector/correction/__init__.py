"""STT post-recognition text correction library."""

# Consumer API
from .builder import build_corrector
from .corrector import SpeechCorrector

# Implementations
from .fuzzy_matcher import FuzzyMatcher

# Framework API
from .languages import LanguageModule
from .languages.registry import LanguageModuleRegistry
from .matchers import DefaultMatcher, PhoneticMatcher

# Learning from mishearings
from .mishearing import Fix, FixPlan, normalize_text, plan_fix
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
    "build_corrector",
    "SpeechCorrector",
    "CorrectionCandidate",
    "CorrectionChange",
    "CorrectionMethod",
    "CorrectionResult",
    "DiagnosticResult",
    # Learning from mishearings
    "Fix",
    "FixPlan",
    "normalize_text",
    "plan_fix",
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
]

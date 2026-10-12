"""Build the three-processor correction pipeline from plain values."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from .corrector import SpeechCorrector
from .defaults import DEFAULT_THRESHOLD
from .languages.registry import LanguageModuleRegistry
from .processors import ReplacementProcessor, SimilarityProcessor, TextProcessor

_LOGGER = logging.getLogger(__name__)


def build_corrector(
    locale: str | None,
    *,
    replacements: Mapping[str, str] | None = None,
    phrases: list[str] | None = None,
    exclusions: list[str] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    language_config: dict[str, dict[str, Any]] | None = None,
    language_processing: bool = True,
    similarity_matching: bool = True,
) -> SpeechCorrector:
    """Build a SpeechCorrector: Language Processing, Replacements, Similarity.

    Args:
        locale: BCP-47 locale of the text (e.g. "zh-TW"), or None if unknown;
            Language Processing runs only for a known locale.
        replacements: Rules mapping a wrong text to its correct text. None or
            empty leaves the Custom Replacements processor out.
        phrases: Known correct phrases for Similarity Matching; replace them
            later with ``SpeechCorrector.update_phrases``.
        exclusions: Segments Similarity Matching never corrects.
        threshold: Minimum similarity (0.0-1.0) to accept a match.
        language_config: Per-language settings keyed by module key
            (e.g. "mandarin"); a missing language uses its defaults.
        language_processing: Whether to run Language Processing.
        similarity_matching: Whether to run Similarity Matching.

    Returns:
        A SpeechCorrector running the enabled processors in order.
    """
    processors: list[TextProcessor] = []

    if language_processing and locale:
        module = LanguageModuleRegistry.get_module_for_locale(locale)
        if module is not None:
            module_cfg = (language_config or {}).get(
                module.module_key(), module.default_config()
            )
            processors.extend(module.get_processors(locale, module_cfg))

    if replacements:
        processors.append(ReplacementProcessor(dict(replacements)))

    if similarity_matching:
        matchers = LanguageModuleRegistry.get_matchers(
            locale, language_config=language_config or None
        )
        _LOGGER.debug("Matchers for locale %s: %s", locale or "unknown", matchers)
        processors.append(
            SimilarityProcessor(
                known_phrases=phrases or [],
                threshold=threshold,
                matchers=matchers,
                exclusions=exclusions or None,
            )
        )

    return SpeechCorrector(processors)

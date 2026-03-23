"""Centralized correction configuration from config entry options."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .const import (
    CONF_AUTO_COLLECT_SOURCES,
    CONF_CUSTOM_EXCLUSIONS,
    CONF_CUSTOM_PHRASES,
    CONF_CUSTOM_REPLACEMENTS,
    CONF_ENABLE_CUSTOM_REPLACEMENTS,
    CONF_ENABLE_FUZZY_MATCHING,
    CONF_FUZZY_THRESHOLD,
    DEFAULT_AUTO_COLLECT_SOURCES,
    DEFAULT_ENABLE_CUSTOM_REPLACEMENTS,
    DEFAULT_ENABLE_FUZZY_MATCHING,
    DEFAULT_FUZZY_THRESHOLD,
)


@dataclass(slots=True)
class CorrectionConfig:
    """Typed configuration for the correction pipeline.

    Centralizes all CONF_*/DEFAULT_* pairings so they are defined once.
    Unlike the azure-speech-stt version, this does NOT include
    enable_entity_hints (Azure pre-recognition hints are not relevant here).
    """

    enable_custom_replacements: bool = DEFAULT_ENABLE_CUSTOM_REPLACEMENTS
    enable_fuzzy_matching: bool = DEFAULT_ENABLE_FUZZY_MATCHING
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD
    custom_phrases: list[str] = field(default_factory=list)
    custom_replacements: dict[str, str] = field(default_factory=dict)
    custom_exclusions: list[str] = field(default_factory=list)
    auto_collect_sources: list[str] = field(
        default_factory=lambda: list(DEFAULT_AUTO_COLLECT_SOURCES)
    )

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> CorrectionConfig:
        """Build from a config entry options dict.

        Args:
            options: Config entry options (MappingProxyType or dict).

        Returns:
            CorrectionConfig populated from options with defaults.
        """
        return cls(
            enable_custom_replacements=options.get(
                CONF_ENABLE_CUSTOM_REPLACEMENTS, DEFAULT_ENABLE_CUSTOM_REPLACEMENTS
            ),
            enable_fuzzy_matching=options.get(
                CONF_ENABLE_FUZZY_MATCHING, DEFAULT_ENABLE_FUZZY_MATCHING
            ),
            fuzzy_threshold=options.get(CONF_FUZZY_THRESHOLD, DEFAULT_FUZZY_THRESHOLD),
            custom_phrases=options.get(CONF_CUSTOM_PHRASES, []),
            custom_replacements=options.get(CONF_CUSTOM_REPLACEMENTS, {}),
            custom_exclusions=options.get(CONF_CUSTOM_EXCLUSIONS, []),
            auto_collect_sources=list(
                options.get(CONF_AUTO_COLLECT_SOURCES, DEFAULT_AUTO_COLLECT_SOURCES)
            ),
        )

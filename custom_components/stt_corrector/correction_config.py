"""Centralized correction configuration from config entry options."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .const import (
    CONF_ACTIVE_PROCESSORS,
    CONF_AUTO_COLLECT_SOURCES,
    CONF_CUSTOM_EXCLUSIONS,
    CONF_CUSTOM_PHRASES,
    CONF_CUSTOM_REPLACEMENTS,
    CONF_FUZZY_THRESHOLD,
    CONF_LANGUAGE_CONFIG,
    CORRECTION_PROCESSOR_LANGUAGE,
    CORRECTION_PROCESSOR_REPLACEMENTS,
    CORRECTION_PROCESSOR_SIMILARITY,
    DEFAULT_ACTIVE_PROCESSORS,
    DEFAULT_AUTO_COLLECT_SOURCES,
    DEFAULT_FUZZY_THRESHOLD,
)


@dataclass(slots=True)
class CorrectionConfig:
    """Typed configuration for the correction pipeline.

    Processor enable states are derived from the active_processors list.
    No redundant boolean flags are stored.
    """

    active_processors: list[str] = field(
        default_factory=lambda: list(DEFAULT_ACTIVE_PROCESSORS)
    )
    fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD
    custom_phrases: list[str] = field(default_factory=list)
    custom_replacements: dict[str, str] = field(default_factory=dict)
    custom_exclusions: list[str] = field(default_factory=list)
    auto_collect_sources: list[str] = field(
        default_factory=lambda: list(DEFAULT_AUTO_COLLECT_SOURCES)
    )
    language_config: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def enable_language_processing(self) -> bool:
        """Whether language processing is enabled."""
        return CORRECTION_PROCESSOR_LANGUAGE in self.active_processors

    @property
    def enable_custom_replacements(self) -> bool:
        """Whether custom replacements are enabled."""
        return CORRECTION_PROCESSOR_REPLACEMENTS in self.active_processors

    @property
    def enable_fuzzy_matching(self) -> bool:
        """Whether similarity matching is enabled."""
        return CORRECTION_PROCESSOR_SIMILARITY in self.active_processors

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> CorrectionConfig:
        """Build from a config entry options dict.

        Args:
            options: Config entry options (MappingProxyType or dict).

        Returns:
            CorrectionConfig populated from options with defaults.
        """
        return cls(
            active_processors=list(
                options.get(CONF_ACTIVE_PROCESSORS, DEFAULT_ACTIVE_PROCESSORS)
            ),
            fuzzy_threshold=options.get(CONF_FUZZY_THRESHOLD, DEFAULT_FUZZY_THRESHOLD),
            custom_phrases=options.get(CONF_CUSTOM_PHRASES, []),
            custom_replacements=options.get(CONF_CUSTOM_REPLACEMENTS, {}),
            custom_exclusions=options.get(CONF_CUSTOM_EXCLUSIONS, []),
            auto_collect_sources=list(
                options.get(CONF_AUTO_COLLECT_SOURCES, DEFAULT_AUTO_COLLECT_SOURCES)
            ),
            language_config=options.get(CONF_LANGUAGE_CONFIG, {}),
        )

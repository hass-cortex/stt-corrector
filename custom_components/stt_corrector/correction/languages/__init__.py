"""Language-specific processing modules for STT correction.

Each language module is self-contained, providing:
- LanguageProcessor implementations (Language Processing)
- PhoneticMatcher implementations (Similarity Matching)
- Per-locale configuration defaults and schema
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..matchers import PhoneticMatcher
from ..processors.base import TextProcessor


def normalize_locale(locale: str) -> str:
    """Normalize a BCP-47 locale to lowercase with hyphen separator.

    HA Voice Pipeline and different STT engines may send locales in various
    formats: "zh-TW", "zh_tw", "zh-tw", "zh_TW". This normalizes them all
    to "zh-tw" for consistent config key lookup.

    Args:
        locale: BCP-47 locale string in any format.

    Returns:
        Lowercase locale with hyphen separator (e.g. "zh-tw").
    """
    return locale.lower().replace("_", "-")


class LanguageModule(ABC):
    """Base class for language-specific processing modules.

    Each language module defines the processors, matchers, and configuration
    for a family of related locales. Subclass this to add a new language.
    """

    @abstractmethod
    def locales(self) -> tuple[str, ...]:
        """Return BCP-47 locale prefixes this module handles."""

    @abstractmethod
    def module_key(self) -> str:
        """Return registry key for config storage (e.g. 'mandarin')."""

    @abstractmethod
    def menu_label(self) -> str:
        """Return display name for options menu (e.g. 'Chinese (中文)')."""

    @abstractmethod
    def default_config(self) -> dict[str, dict[str, Any]]:
        """Return per-locale default settings.

        Returns:
            Dict mapping lowercase locale to settings dict.
            e.g. {"zh-tw": {"script_conversion": "s2tw", "pinyin_matching": True}}
        """

    @abstractmethod
    def get_processors(
        self, locale: str, config: dict[str, dict[str, Any]]
    ) -> list[TextProcessor]:
        """Return Language Processing processors for the given locale.

        Args:
            locale: BCP-47 locale code (e.g. "zh-TW").
            config: Per-locale config dict from options.

        Returns:
            Ordered list of processors to apply. Empty if none enabled.
        """

    @abstractmethod
    def get_matcher(
        self, locale: str, config: dict[str, dict[str, Any]]
    ) -> PhoneticMatcher | None:
        """Return a Similarity Matching phonetic matcher for the given locale, or None.

        Args:
            locale: BCP-47 locale code (e.g. "zh-TW").
            config: Per-locale config dict from options.
        """

    @abstractmethod
    def config_schema(self) -> dict[str, list[str]]:
        """Return per-locale setting names for config flow schema generation.

        Returns:
            Dict mapping lowercase locale to list of setting names.
            e.g. {"zh-tw": ["script_conversion", "pinyin_matching"]}
        """

    def select_options(self) -> dict[str, list[dict[str, str]]]:
        """Return select options for settings rendered as dropdowns.

        Settings listed here are rendered as dropdown selectors in the
        config flow instead of checkboxes or text fields.

        Returns:
            Dict mapping setting name to list of {value, label} dicts.
            Settings not in this dict use default field types.
        """
        return {}


__all__ = ["LanguageModule", "TextProcessor", "PhoneticMatcher", "normalize_locale"]

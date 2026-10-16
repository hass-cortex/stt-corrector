"""Registry of language modules for locale-based dispatch.

To add a new language, create a LanguageModule subclass and add it
to LanguageModuleRegistry._modules -- no other file changes required
for core pipeline integration.
"""

from __future__ import annotations

from typing import Any

from ..matchers import DefaultMatcher, PhoneticMatcher
from . import LanguageModule
from .mandarin import MandarinModule


class LanguageModuleRegistry:
    """Registry mapping BCP-47 locales to LanguageModule instances."""

    _modules: tuple[LanguageModule, ...] = (MandarinModule(),)

    @classmethod
    def get_module_for_locale(cls, locale: str) -> LanguageModule | None:
        """Find the module that handles the given locale prefix.

        Args:
            locale: BCP-47 locale code (e.g. "zh-TW", "en-US").

        Returns:
            The matching LanguageModule, or None.
        """
        for module in cls._modules:
            if module.canonical_locale(locale) is not None:
                return module
        return None

    @classmethod
    def canonical_locale(cls, locale: str, country: str | None = None) -> str:
        """Return the module locale a tag means (zh-Hant -> zh-TW), else the tag.

        Args:
            locale: BCP-47 locale as the pipeline sent it.
            country: HA's configured country, for a tag with no region.
        """
        for module in cls._modules:
            if (canonical := module.canonical_locale(locale, country)) is not None:
                return canonical
        return locale

    @classmethod
    def get_module_by_key(cls, key: str) -> LanguageModule | None:
        """Find a module by its registry key.

        Args:
            key: Module key (e.g. "mandarin").

        Returns:
            The matching LanguageModule, or None.
        """
        for module in cls._modules:
            if module.module_key() == key:
                return module
        return None

    @classmethod
    def all_modules(cls) -> list[LanguageModule]:
        """Return all registered language modules."""
        return list(cls._modules)

    @classmethod
    def get_matchers(
        cls,
        locale: str | None,
        language_config: dict[str, dict[str, Any]] | None = None,
    ) -> list[PhoneticMatcher]:
        """Build an ordered matcher list for the given locale.

        Args:
            locale: BCP-47 locale code, or None for all matchers.
            language_config: Per-module language config from options.

        Returns:
            Ordered list of matchers. DefaultMatcher is always last.
        """
        matchers: list[PhoneticMatcher] = []

        if locale is None:
            for module in cls._modules:
                config = language_config or {}
                module_cfg = config.get(module.module_key(), module.default_config())
                matcher = module.get_matcher(None, module_cfg)
                if matcher is not None:
                    matchers.append(matcher)
        else:
            locale_module = cls.get_module_for_locale(locale)
            if locale_module is not None:
                config = language_config or {}
                module_cfg = config.get(
                    locale_module.module_key(), locale_module.default_config()
                )
                matcher = locale_module.get_matcher(locale, module_cfg)
                if matcher is not None:
                    matchers.append(matcher)

        matchers.append(DefaultMatcher())
        return matchers

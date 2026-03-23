"""Locale-to-matcher registry for phonetic correction.

Maps BCP-47 locale prefixes to PhoneticMatcher implementations.
To add a new language, add an entry to MatcherRegistry._language_matchers —
no other file changes required.

When locale is None (unknown), all registered matchers are included
so that supports() can select at runtime.
"""

from __future__ import annotations

from .languages.mandarin import PinyinMatcher
from .matchers import DefaultMatcher, PhoneticMatcher


class MatcherRegistry:
    """Registry mapping BCP-47 locale prefixes to PhoneticMatcher classes.

    To add a new language, add an entry to _language_matchers.
    DefaultMatcher is always appended as fallback.
    """

    # (locale_prefixes, matcher_class) — evaluated in order.
    # A locale matching multiple entries gets all corresponding matchers.
    _language_matchers: list[tuple[tuple[str, ...], type[PhoneticMatcher]]] = [
        (("zh-CN", "zh-TW"), PinyinMatcher),
    ]

    @classmethod
    def get_matchers(cls, locale: str | None) -> list[PhoneticMatcher]:
        """Build an ordered matcher list for the given locale.

        Args:
            locale: BCP-47 locale code (e.g. "zh-CN", "en-US"), or None.
                    When None, all registered matchers are included.

        Returns:
            Ordered list of matchers. DefaultMatcher is always appended last.
        """
        matchers: list[PhoneticMatcher] = []

        if locale is None:
            # Unknown locale — include all registered matchers
            for _, matcher_cls in cls._language_matchers:
                matchers.append(matcher_cls())
        else:
            # HA Voice Pipeline normalizes locales to lowercase (zh-tw, not zh-TW)
            locale_lower = locale.lower()
            for prefixes, matcher_cls in cls._language_matchers:
                if any(locale_lower.startswith(p.lower()) for p in prefixes):
                    matchers.append(matcher_cls())

        matchers.append(DefaultMatcher())
        return matchers

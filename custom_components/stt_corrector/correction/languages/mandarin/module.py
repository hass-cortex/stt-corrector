"""MandarinModule: the Chinese locales' settings, processors and matcher."""

from __future__ import annotations

from typing import Any

from pypinyin import lazy_pinyin

from ...processors.base import TextProcessor
from ...processors.punctuation import TrailingPunctuationStripper
from .. import LanguageModule, normalize_locale
from .pinyin import PinyinMatcher
from .script import OPENCC_MODES, ChineseScriptConverter, get_opencc
from .taiwan_readings import get_taiwan_readings

# Per-locale setting names
SETTING_STRIP_TRAILING_PUNCTUATION = "strip_trailing_punctuation"
SETTING_TRAILING_PUNCTUATION = "trailing_punctuation"
SETTING_SCRIPT_CONVERSION = "script_conversion"
SETTING_PINYIN_MATCHING = "pinyin_matching"
SETTING_TAIWAN_READINGS = "taiwan_readings"

_SETTINGS: list[str] = [
    SETTING_STRIP_TRAILING_PUNCTUATION,
    SETTING_TRAILING_PUNCTUATION,
    SETTING_SCRIPT_CONVERSION,
    SETTING_PINYIN_MATCHING,
]

# Settings only some locales offer, with their defaults
_LOCALE_ONLY_SETTINGS: dict[str, dict[str, Any]] = {
    "zh-tw": {SETTING_TAIWAN_READINGS: True},
}

# Default OpenCC mode per locale
_DEFAULT_OPENCC_MODES: dict[str, str] = {
    "zh-tw": "s2tw",
    "zh-hk": "s2hk",
    "zh-cn": "",
}

# Shared base config (locale-specific defaults override script_conversion)
_BASE_LOCALE_CONFIG: dict[str, Any] = {
    SETTING_STRIP_TRAILING_PUNCTUATION: True,
    SETTING_TRAILING_PUNCTUATION: "。",
    SETTING_SCRIPT_CONVERSION: "",
    SETTING_PINYIN_MATCHING: True,
}

_LOCALES = ("zh-TW", "zh-HK", "zh-CN")

# Subtags that name each locale; a region wins over a script (zh-Hant-HK).
_REGION_LOCALES: dict[str, str] = {
    "tw": "zh-TW",
    "hk": "zh-HK",
    "mo": "zh-HK",
    "cn": "zh-CN",
    "sg": "zh-CN",
}
# Hant alone could be Taiwan or Hong Kong; Taiwan is the default.
_SCRIPT_LOCALES: dict[str, str] = {"hant": "zh-TW", "hans": "zh-CN"}
# The script a wrapped STT may offer instead of the region.
_LOCALE_SCRIPTS: dict[str, str] = {
    "zh-tw": "zh-hant",
    "zh-hk": "zh-hant",
    "zh-cn": "zh-hans",
}


class MandarinModule(LanguageModule):
    """Chinese language module with script conversion and pinyin matching.

    Handles zh-TW, zh-HK, and zh-CN locales with:
    - Language Processing: Trailing punctuation stripping + script conversion (OpenCC)
    - Similarity Matching: Pinyin-based phonetic matching for similarity correction
    """

    def locales(self) -> tuple[str, ...]:
        return _LOCALES

    def module_key(self) -> str:
        return "mandarin"

    def menu_label(self) -> str:
        return "Chinese (中文)"

    def default_config(self) -> dict[str, dict[str, Any]]:
        return {
            locale: {
                **_BASE_LOCALE_CONFIG,
                SETTING_SCRIPT_CONVERSION: _DEFAULT_OPENCC_MODES.get(locale, ""),
                **_LOCALE_ONLY_SETTINGS.get(locale, {}),
            }
            for locale in (normalize_locale(loc) for loc in _LOCALES)
        }

    def canonical_locale(self, locale: str, country: str | None = None) -> str | None:
        """Map any Chinese tag (zh, zh-Hant, zh-SG, cmn-TW, ...) onto a locale.

        A tag with neither region nor script follows HA's country, then zh-CN.
        """
        language, *subtags = normalize_locale(locale).split("-")
        if language not in ("zh", "cmn"):
            return None
        for subtag in subtags:
            if subtag in _REGION_LOCALES:
                return _REGION_LOCALES[subtag]
        for subtag in subtags:
            if subtag in _SCRIPT_LOCALES:
                return _SCRIPT_LOCALES[subtag]
        return _REGION_LOCALES.get((country or "").lower(), "zh-CN")

    def default_stt_language(self, locale: str, available_languages: list[str]) -> str:
        """Prefer the exact locale, then its script (zh-TW -> zh-Hant), then zh."""
        by_normalized = {normalize_locale(lang): lang for lang in available_languages}
        normalized = normalize_locale(self.canonical_locale(locale) or locale)
        for candidate in (normalized, _LOCALE_SCRIPTS.get(normalized), "zh"):
            if candidate is not None and candidate in by_normalized:
                return by_normalized[candidate]
        return ""

    def get_processors(
        self, locale: str, config: dict[str, dict[str, Any]]
    ) -> list[TextProcessor]:
        normalized = normalize_locale(self.canonical_locale(locale) or locale)
        locale_cfg = config.get(normalized, {})
        processors: list[TextProcessor] = []

        if locale_cfg.get(SETTING_STRIP_TRAILING_PUNCTUATION, True):
            punctuation = locale_cfg.get(SETTING_TRAILING_PUNCTUATION, "。")
            if punctuation:
                processors.append(TrailingPunctuationStripper(punctuation))

        mode = locale_cfg.get(SETTING_SCRIPT_CONVERSION, "")
        if isinstance(mode, bool):
            mode = _DEFAULT_OPENCC_MODES.get(normalized, "")
        if mode:
            processors.append(ChineseScriptConverter(mode))

        return processors

    def get_matcher(
        self, locale: str | None, config: dict[str, dict[str, Any]]
    ) -> PinyinMatcher | None:
        if locale is None:
            # Locale unknown: no zh-TW-only Taiwan readings
            enabled = any(
                config.get(normalize_locale(loc), {}).get(SETTING_PINYIN_MATCHING, True)
                for loc in _LOCALES
            )
            return PinyinMatcher() if enabled else None
        normalized = normalize_locale(self.canonical_locale(locale) or locale)
        locale_cfg = config.get(normalized, {})
        if not locale_cfg.get(SETTING_PINYIN_MATCHING, True):
            return None
        locale_only = _LOCALE_ONLY_SETTINGS.get(normalized, {})
        if SETTING_TAIWAN_READINGS in locale_only and locale_cfg.get(
            SETTING_TAIWAN_READINGS, locale_only[SETTING_TAIWAN_READINGS]
        ):
            return PinyinMatcher(get_taiwan_readings())
        return PinyinMatcher()

    def config_schema(self) -> dict[str, list[str]]:
        return {
            locale: [*_SETTINGS, *_LOCALE_ONLY_SETTINGS.get(locale, {})]
            for locale in (normalize_locale(loc) for loc in _LOCALES)
        }

    def preload(self) -> None:
        """Load pypinyin's dictionaries, OpenCC tables and Taiwan readings."""
        lazy_pinyin("")  # pypinyin reads phrases_dict.json on first use
        for mode in OPENCC_MODES:
            get_opencc(mode)
        get_taiwan_readings()

    def select_options(self) -> dict[str, list[dict[str, str]]]:
        return {
            SETTING_SCRIPT_CONVERSION: [
                {"value": "", "label": "Off"},
                {"value": "s2tw", "label": "Simplified → Traditional (Taiwan)"},
                {"value": "s2hk", "label": "Simplified → Traditional (Hong Kong)"},
                {"value": "t2s", "label": "Traditional → Simplified"},
            ],
        }

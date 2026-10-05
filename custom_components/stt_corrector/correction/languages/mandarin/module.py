"""MandarinModule: the Chinese locales' settings, processors and matcher."""

from __future__ import annotations

from typing import Any

from pypinyin import lazy_pinyin

from ...processors.base import TextProcessor
from ...processors.punctuation import TrailingPunctuationStripper
from .. import LanguageModule, normalize_locale
from .pinyin import PinyinMatcher
from .script import OPENCC_MODES, ChineseScriptConverter, get_opencc

# Per-locale setting names
SETTING_STRIP_TRAILING_PUNCTUATION = "strip_trailing_punctuation"
SETTING_TRAILING_PUNCTUATION = "trailing_punctuation"
SETTING_SCRIPT_CONVERSION = "script_conversion"
SETTING_PINYIN_MATCHING = "pinyin_matching"

_SETTINGS: list[str] = [
    SETTING_STRIP_TRAILING_PUNCTUATION,
    SETTING_TRAILING_PUNCTUATION,
    SETTING_SCRIPT_CONVERSION,
    SETTING_PINYIN_MATCHING,
]

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
            }
            for locale in (normalize_locale(loc) for loc in _LOCALES)
        }

    def get_processors(
        self, locale: str, config: dict[str, dict[str, Any]]
    ) -> list[TextProcessor]:
        normalized = normalize_locale(locale)
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
        self, locale: str, config: dict[str, dict[str, Any]]
    ) -> PinyinMatcher | None:
        normalized = normalize_locale(locale)
        locale_cfg = config.get(normalized, {})
        if not locale_cfg.get(SETTING_PINYIN_MATCHING, True):
            return None
        return PinyinMatcher()

    def config_schema(self) -> dict[str, list[str]]:
        return {normalize_locale(loc): list(_SETTINGS) for loc in _LOCALES}

    def preload(self) -> None:
        """Load pypinyin's dictionaries and OpenCC tables."""
        lazy_pinyin("")  # pypinyin reads phrases_dict.json on first use
        for mode in OPENCC_MODES:
            get_opencc(mode)

    def select_options(self) -> dict[str, list[dict[str, str]]]:
        return {
            SETTING_SCRIPT_CONVERSION: [
                {"value": "", "label": "Off"},
                {"value": "s2tw", "label": "Simplified → Traditional (Taiwan)"},
                {"value": "s2hk", "label": "Simplified → Traditional (Hong Kong)"},
                {"value": "t2s", "label": "Traditional → Simplified"},
            ],
        }

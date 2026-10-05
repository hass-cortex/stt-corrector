"""Chinese script conversion (Simplified/Traditional) via OpenCC."""

from __future__ import annotations

from typing import Any

from ...processors.base import TextProcessor
from ...types import CorrectionChange, CorrectionMethod

# All OpenCC modes that may be selected by users (used for preloading)
OPENCC_MODES: frozenset[str] = frozenset({"s2tw", "s2hk", "t2s"})

# OpenCC converter cache (immutable conversion tables, safe to reuse)
_opencc_cache: dict[str, Any] = {}


def get_opencc(mode: str) -> Any:
    """Get or create a cached OpenCC converter instance.

    Must be called from an executor thread on first use, since OpenCC()
    performs blocking file I/O to load its config JSON.
    Subsequent calls return the cached instance and are safe from any thread.
    """
    if mode not in _opencc_cache:
        from opencc import OpenCC

        _opencc_cache[mode] = OpenCC(mode)
    return _opencc_cache[mode]


class ChineseScriptConverter(TextProcessor):
    """Chinese simplified/traditional script conversion using OpenCC.

    Converts text between simplified and traditional Chinese at the
    character level (e.g., "开灯" -> "開燈" for s2tw mode).

    Accepts any OpenCC conversion mode (e.g., s2tw, s2hk, t2s, tw2s, hk2s).
    See https://github.com/BYVoid/OpenCC for the full list.
    """

    def __init__(self, mode: str) -> None:
        self._converter = get_opencc(mode)
        self._mode = mode

    def process(self, text: str) -> tuple[str, list[CorrectionChange]]:
        """Convert text between simplified and traditional Chinese.

        Args:
            text: Input text to convert.

        Returns:
            Tuple of (converted_text, list_of_changes).
        """
        if not text:
            return text, []

        converted = self._converter.convert(text)
        if converted == text:
            return text, []

        return converted, [
            CorrectionChange(
                original_segment=text,
                corrected_segment=converted,
                method=CorrectionMethod.SCRIPT_CONVERSION,
                confidence=1.0,
            )
        ]

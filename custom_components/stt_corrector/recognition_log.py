"""Recent recognitions per corrector, persisted across restarts.

A reported mishearing is matched against these to find the corrector that
heard it, its raw STT text and locale; the rest serve as the regression
texts a learned fix must leave unchanged.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .mishearing import normalize_text

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

MAX_RECOGNITIONS = 100
_STORAGE_VERSION = 1
_SAVE_DELAY = 10


@dataclass(frozen=True, slots=True)
class Recognition:
    """One successful recognition: the STT text and what it corrected to."""

    raw: str
    corrected: str
    locale: str
    at: str


class RecognitionLog:
    """The most recent recognitions of one corrector, newest last."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[list[dict[str, Any]]] = Store(
            hass, _STORAGE_VERSION, _storage_key(entry_id)
        )
        self._items: deque[Recognition] = deque(maxlen=MAX_RECOGNITIONS)

    async def async_load(self) -> None:
        """Restore the saved recognitions."""
        for item in await self._store.async_load() or []:
            self._items.append(Recognition(**item))

    def add(self, raw: str, corrected: str, locale: str) -> None:
        """Record a recognition; saved after a short delay."""
        self._items.append(
            Recognition(raw, corrected, locale, dt_util.utcnow().isoformat())
        )
        self._store.async_delay_save(
            lambda: [asdict(item) for item in self._items], _SAVE_DELAY
        )

    def find(self, text: str) -> Recognition | None:
        """The newest recognition whose corrected or raw text is ``text``."""
        target = normalize_text(text)
        for item in reversed(self._items):
            if target in (normalize_text(item.corrected), normalize_text(item.raw)):
                return item
        return None

    def raw_texts(self, locale: str) -> list[str]:
        """Raw STT texts recognized in ``locale``, oldest first, deduplicated."""
        return list(
            dict.fromkeys(item.raw for item in self._items if item.locale == locale)
        )

    @staticmethod
    async def async_remove(hass: HomeAssistant, entry_id: str) -> None:
        """Delete a removed entry's saved recognitions."""
        await Store(hass, _STORAGE_VERSION, _storage_key(entry_id)).async_remove()


def _storage_key(entry_id: str) -> str:
    return f"{DOMAIN}.recognitions.{entry_id}"

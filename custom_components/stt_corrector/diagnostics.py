"""Diagnostics support for STT Corrector."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import STTCorrectorConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: STTCorrectorConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "config_entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
    }

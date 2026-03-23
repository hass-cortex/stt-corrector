"""Shared helpers for STT Corrector integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import STTCorrectorRuntimeData


def find_corrected_stt_entity(
    hass: HomeAssistant, entry: ConfigEntry | None = None
) -> Any | None:
    """Find a CorrectedSTTEntity instance via runtime_data.

    Args:
        hass: Home Assistant instance.
        entry: If provided, find the entity for this specific config entry.
               If None, return the first STT corrector entity found.

    Returns:
        The CorrectedSTTEntity instance, or None if not found.
    """
    if entry is not None:
        runtime_data: STTCorrectorRuntimeData | None = getattr(
            entry, "runtime_data", None
        )
        if runtime_data is not None:
            return runtime_data.entity
        return None

    # No entry specified — search all config entries for this domain
    for cfg_entry in hass.config_entries.async_entries(DOMAIN):
        runtime_data = getattr(cfg_entry, "runtime_data", None)
        if isinstance(runtime_data, STTCorrectorRuntimeData):
            return runtime_data.entity

    return None

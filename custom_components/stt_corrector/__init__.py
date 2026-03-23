"""STT Corrector — post-recognition correction for any STT entity."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .models import STTCorrectorRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: Final = ["stt", "sensor"]


def _preload_pypinyin() -> None:
    """Pre-load pypinyin in executor to avoid blocking I/O in event loop.

    pypinyin reads pinyin_dict.json on import and phrases_dict.json on first
    lazy_pinyin() call — both trigger blocking open(). Loading them here
    (in a thread) ensures subsequent calls from the event loop are instant.
    """
    from pypinyin import lazy_pinyin

    lazy_pinyin("")  # force-load phrases_dict.json


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up STT Corrector from a config entry."""
    await hass.async_add_executor_job(_preload_pypinyin)

    entry.runtime_data = STTCorrectorRuntimeData()

    # Forward to STT and sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Rebuild corrector when options change (e.g., via services)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    # Register services (once per domain)
    from .const import DOMAIN

    if not hass.services.has_service(DOMAIN, "test_correction"):
        from .services import async_register_services

        async_register_services(hass)

    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — rebuild corrector and phrase builder."""
    from .helpers import find_corrected_stt_entity

    entity = find_corrected_stt_entity(hass, entry)
    if entity:
        entity.rebuild_from_options()
        _LOGGER.debug("Rebuilt corrector after options update")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an STT Corrector config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

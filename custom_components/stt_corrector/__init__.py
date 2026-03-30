"""STT Corrector — post-recognition correction for any STT entity."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .models import STTCorrectorRuntimeData

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type STTCorrectorConfigEntry = ConfigEntry[STTCorrectorRuntimeData]

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


def _preload_opencc() -> None:
    """Pre-load OpenCC in executor to avoid blocking I/O in event loop.

    OpenCC reads conversion tables on first use, which triggers blocking I/O.
    Loading here (in a thread) ensures subsequent calls are instant.
    """
    from opencc import OpenCC

    OpenCC("s2tw")  # force-load conversion tables


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up STT Corrector integration."""
    from .services import async_register_services

    async_register_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: STTCorrectorConfigEntry
) -> bool:
    """Set up STT Corrector from a config entry."""
    await asyncio.gather(
        hass.async_add_executor_job(_preload_pypinyin),
        hass.async_add_executor_job(_preload_opencc),
    )

    entry.runtime_data = STTCorrectorRuntimeData()

    # Forward to STT and sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Rebuild corrector when options change (e.g., via services)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(
    hass: HomeAssistant, entry: STTCorrectorConfigEntry
) -> None:
    """Handle options update — rebuild corrector and phrase builder."""
    from .helpers import find_corrected_stt_entity

    entity = find_corrected_stt_entity(hass, entry)
    if entity:
        entity.rebuild_from_options()
        _LOGGER.debug("Rebuilt corrector after options update")


async def async_unload_entry(
    hass: HomeAssistant, entry: STTCorrectorConfigEntry
) -> bool:
    """Unload an STT Corrector config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

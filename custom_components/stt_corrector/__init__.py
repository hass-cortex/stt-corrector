"""STT Corrector — post-recognition correction for any STT entity."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_WRAPPED_ENTITY_ID, DOMAIN
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
    Loading here (in a thread) populates the mandarin module's cache so
    subsequent calls from the event loop are instant.
    """
    from .correction.languages.mandarin import OPENCC_MODES, _get_opencc

    for mode in OPENCC_MODES:
        _get_opencc(mode)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up STT Corrector integration."""
    from .services import async_register_services

    async_register_services(hass)

    # Global preloads — shared across all entries, only once
    await asyncio.gather(
        hass.async_add_executor_job(_preload_pypinyin),
        hass.async_add_executor_job(_preload_opencc),
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: STTCorrectorConfigEntry
) -> bool:
    """Set up STT Corrector from a config entry."""
    entry.runtime_data = STTCorrectorRuntimeData(
        wrapped_entity_id=entry.data.get(CONF_WRAPPED_ENTITY_ID)
    )

    # Forward to STT and sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # The single path for every entry update: options flow, services,
    # reconfigure and the repair flow all land here.
    entry.async_on_unload(entry.add_update_listener(_async_update_entry))

    return True


async def _async_update_entry(
    hass: HomeAssistant, entry: STTCorrectorConfigEntry
) -> None:
    """Apply an entry update: reload on a new wrapped entity, else rebuild.

    The wrapped entity is wired in at setup (registry tracking, repair
    issue), so swapping it needs a reload; option changes rebuild the
    corrector in place.
    """
    from .helpers import find_corrected_stt_entity

    if entry.data.get(CONF_WRAPPED_ENTITY_ID) != entry.runtime_data.wrapped_entity_id:
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return

    entity = find_corrected_stt_entity(hass, entry)
    if entity:
        entity.rebuild_from_options()
        _LOGGER.debug("Rebuilt corrector after options update")


async def async_unload_entry(
    hass: HomeAssistant, entry: STTCorrectorConfigEntry
) -> bool:
    """Unload an STT Corrector config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: STTCorrectorConfigEntry
) -> None:
    """Clear the entry's repair issue on removal.

    Only `stt.py` clears it otherwise, and only when the wrapped entity is
    found — so deleting a broken entry from the integrations page would
    strand a fixable issue whose fix flow can no longer resolve the entry.
    """
    from homeassistant.helpers import issue_registry as ir

    from .repairs import wrapped_entity_issue_id

    ir.async_delete_issue(hass, DOMAIN, wrapped_entity_issue_id(entry.entry_id))

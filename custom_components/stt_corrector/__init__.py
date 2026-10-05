"""STT Corrector — post-recognition correction for any STT entity."""

from __future__ import annotations

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


def _preload_language_modules() -> None:
    """Load every language module's blocking resources, in an executor thread.

    Importing the modules here, not at the top, keeps their library imports
    (pypinyin reads its dictionary on import) off the event loop too.
    """
    from .correction.languages.registry import LanguageModuleRegistry

    for module in LanguageModuleRegistry.all_modules():
        module.preload()
        _LOGGER.debug("Preloaded language module %s", module.module_key())


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up STT Corrector integration."""
    from .services import async_register_services

    async_register_services(hass)

    # Global preload — shared across all entries, only once
    await hass.async_add_executor_job(_preload_language_modules)
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
    """Clear the entry's repair issue and saved recognitions on removal.

    Only `stt.py` clears the issue otherwise, and only when the wrapped
    entity is found — so deleting a broken entry from the integrations page
    would strand a fixable issue whose fix flow can no longer resolve it.
    """
    from homeassistant.helpers import issue_registry as ir

    from .recognition_log import RecognitionLog
    from .repairs import wrapped_entity_issue_id

    ir.async_delete_issue(hass, DOMAIN, wrapped_entity_issue_id(entry.entry_id))
    await RecognitionLog.async_remove(hass, entry.entry_id)

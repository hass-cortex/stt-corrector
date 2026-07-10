"""Repairs support for STT Corrector.

When a wrapped STT entity disappears (its integration was removed, or a
backend renamed its models), the corrected entity keeps its identity but
can no longer proxy audio. `stt.py` raises a fixable repair issue for
that state; the fix flow below lets the user pick a replacement source
in place — preserving the entry, the corrected entity's id, all
correction options, and therefore every voice pipeline referencing it.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .config_flow import _get_stt_entities
from .const import CONF_WRAPPED_ENTITY_ID

_LOGGER = logging.getLogger(__name__)

ISSUE_WRAPPED_ENTITY_MISSING = "wrapped_entity_missing"


def wrapped_entity_issue_id(entry_id: str) -> str:
    """Stable issue id for the wrapped-entity-missing issue of an entry."""
    return f"{ISSUE_WRAPPED_ENTITY_MISSING}_{entry_id}"


class WrappedEntityMissingRepairFlow(RepairsFlow):
    """Fix flow: pick a new wrapped STT entity for a broken entry."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize with the config entry whose source vanished."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Select the replacement wrapped entity and rewire the entry."""
        stt_options = _get_stt_entities(self.hass)

        # The repairs framework passes the ISSUE DATA dict (not None) on
        # the first invocation, so "is not None" cannot distinguish
        # form-shown from form-submitted — key presence can.
        if user_input is not None and CONF_WRAPPED_ENTITY_ID in user_input:
            entity_id = user_input[CONF_WRAPPED_ENTITY_ID]
            state = self.hass.states.get(entity_id)
            friendly_name = (
                state.attributes.get("friendly_name", entity_id)
                if state is not None
                else entity_id
            )
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={CONF_WRAPPED_ENTITY_ID: entity_id},
                title=f"{friendly_name} Corrected",
                unique_id=entity_id,
            )
            self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
            _LOGGER.info(
                "Rewired %s to wrap %s via repair flow",
                self._entry.entry_id,
                entity_id,
            )
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(CONF_WRAPPED_ENTITY_ID): SelectSelector(
                    SelectSelectorConfig(options=stt_options)
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "title": self._entry.title,
                "wrapped_entity_id": str(
                    self._entry.data.get(CONF_WRAPPED_ENTITY_ID, "")
                ),
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create the fix flow for a wrapped-entity-missing issue."""
    entry = None
    if data and data.get("entry_id"):
        entry = hass.config_entries.async_get_entry(str(data["entry_id"]))
    if entry is None:
        raise ValueError(f"cannot create fix flow for unknown issue {issue_id}")
    return WrappedEntityMissingRepairFlow(entry)

"""Repairs support for STT Corrector.

When a wrapped STT entity disappears (its integration was removed, or a
backend renamed its models), the corrected entity keeps its identity but
can no longer proxy audio. `stt.py` raises a fixable repair issue for
that state, and the fix flow below offers the two ways out:

- **replace** — rewire to another source in place, preserving the entry,
  the corrected entity's id, all correction options, and therefore every
  voice pipeline referencing it. Right when a backend was renamed or
  reinstalled.
- **remove** — delete the entry. Right when the source is gone for good,
  e.g. the user uninstalled that STT model on purpose.

Either outcome clears the issue: the repairs framework deletes it when a
fix flow completes, and `async_remove_entry` covers the case where the
entry is deleted from the integrations page instead.
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
    """Fix flow: rewire a broken entry to a new source, or drop it."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize with the config entry whose source vanished."""
        self._entry = entry

    def _placeholders(self) -> dict[str, str]:
        """Describe the broken entry for every step's copy."""
        return {
            "title": self._entry.title,
            "wrapped_entity_id": str(self._entry.data.get(CONF_WRAPPED_ENTITY_ID, "")),
        }

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Offer both exits: a source vanishing has two distinct causes.

        A renamed or reinstalled backend wants the entry rewired; a model
        the user deliberately deleted wants the corrector gone with it.
        Offering only the former forces a wrong pairing.
        """
        return self.async_show_menu(
            step_id="init",
            menu_options=["replace", "remove"],
            description_placeholders=self._placeholders(),
        )

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Confirm, then delete the config entry outright."""
        if user_input is None:
            return self.async_show_form(
                step_id="remove",
                data_schema=vol.Schema({}),
                description_placeholders=self._placeholders(),
            )
        entry_id = self._entry.entry_id
        await self.hass.config_entries.async_remove(entry_id)
        _LOGGER.info("Removed %s via repair flow", entry_id)
        return self.async_create_entry(title="", data={})

    async def async_step_replace(
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
            step_id="replace",
            data_schema=schema,
            description_placeholders=self._placeholders(),
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

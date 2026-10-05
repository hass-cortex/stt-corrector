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

A learned replacement rule (from `report_mishearing`) is also raised here,
for approval: a rule rewrites its text in every sentence, so the user
decides. Submitting re-plans first and applies only a fix that still
validates; ignoring the issue rejects the rule for good.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import probatio
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .config_flow import _get_stt_entities
from .const import CONF_WRAPPED_ENTITY_ID
from .models import STTCorrectorRuntimeData

_LOGGER = logging.getLogger(__name__)

ISSUE_WRAPPED_ENTITY_MISSING = "wrapped_entity_missing"
ISSUE_LEARNED_RULE = "learned_rule"


def wrapped_entity_issue_id(entry_id: str) -> str:
    """Stable issue id for the wrapped-entity-missing issue of an entry."""
    return f"{ISSUE_WRAPPED_ENTITY_MISSING}_{entry_id}"


def learned_rule_issue_id(entry_id: str, wrong: str) -> str:
    """Stable issue id for a learned rule proposal (one per rule key)."""
    key = hashlib.sha1(wrong.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"{ISSUE_LEARNED_RULE}_{entry_id}_{key}"


class LearnedRuleRepairFlow(RepairsFlow):
    """Fix flow: approve a replacement rule learned from a mishearing."""

    def __init__(self, entry: ConfigEntry, data: dict[str, Any]) -> None:
        """Initialize with the entry and the proposal's issue data."""
        self._entry = entry
        self._data = data

    def _placeholders(self) -> dict[str, str]:
        return {
            key: str(self._data[key]) for key in ("heard", "meant", "wrong", "right")
        } | {"title": self._entry.title}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """The framework passes the issue data here; show the confirmation."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Confirm, then re-plan and apply the approved rule if it still holds.

        Re-planning may find a phrase now does it (safer, applied instead) or
        that nothing is needed; a different rule was not what was approved.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=probatio.Schema({}),
                description_placeholders=self._placeholders(),
            )

        from .services import async_apply_learned_fix

        runtime_data = getattr(self._entry, "runtime_data", None)
        if not isinstance(runtime_data, STTCorrectorRuntimeData) or (
            runtime_data.entity is None
        ):
            return self.async_abort(reason="entity_not_loaded")
        entity = runtime_data.entity
        heard, meant = str(self._data["heard"]), str(self._data["meant"])
        plan = await entity.async_plan_mishearing_fix(
            str(self._data["raw"]), meant, str(self._data["locale"])
        )
        approved = (str(self._data["wrong"]), str(self._data["right"]))
        fix = plan.fix
        if fix is not None and (
            fix.kind == "phrase" or (fix.wrong, fix.right) == approved
        ):
            await async_apply_learned_fix(
                self.hass, entity.entity_id, heard, meant, plan
            )
        elif plan.status != "already_corrected":
            reason = (
                plan.reason or f"it now plans {fix.describe() if fix else 'nothing'}"
            )
            return self.async_abort(
                reason="learned_rule_invalid",
                description_placeholders={"reason": reason},
            )
        return self.async_create_entry(title="", data={})


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
                data_schema=probatio.Schema({}),
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
            _LOGGER.info(
                "Rewired %s to wrap %s via repair flow",
                self._entry.entry_id,
                entity_id,
            )
            return self.async_create_entry(title="", data={})

        schema = probatio.Schema(
            {
                probatio.Required(CONF_WRAPPED_ENTITY_ID): SelectSelector(
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
    """Create the fix flow for an STT Corrector issue."""
    entry = None
    if data and data.get("entry_id"):
        entry = hass.config_entries.async_get_entry(str(data["entry_id"]))
    if entry is None:
        raise ValueError(f"cannot create fix flow for unknown issue {issue_id}")
    if issue_id.startswith(f"{ISSUE_LEARNED_RULE}_"):
        return LearnedRuleRepairFlow(entry, dict(data or {}))
    return WrappedEntityMissingRepairFlow(entry)

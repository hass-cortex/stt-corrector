"""Tests for the wrapped-entity-missing repair flow."""

from unittest.mock import MagicMock

import pytest

from custom_components.stt_corrector.repairs import (
    WrappedEntityMissingRepairFlow,
    async_create_fix_flow,
    wrapped_entity_issue_id,
)


def _make_entity_entry(entity_id, platform="azure_stt"):
    entry = MagicMock()
    entry.entity_id = entity_id
    entry.domain = "stt"
    entry.platform = platform
    entry.original_name = entity_id.split(".")[1]
    entry.name = None
    entry.disabled_by = None
    return entry


def _entry(entry_id="entry-1", wrapped="stt.gone_source"):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.title = "Gone Source Corrected"
    entry.data = {"wrapped_entity_id": wrapped}
    return entry


def _registry_with(entity_ids):
    import homeassistant.helpers.entity_registry as er

    ent_reg = MagicMock()
    ent_reg.entities.values.return_value = [_make_entity_entry(e) for e in entity_ids]
    er.async_get.return_value = ent_reg
    return ent_reg


class TestWrappedEntityMissingRepairFlow:
    @pytest.mark.asyncio
    async def test_shows_form(self, mock_hass):
        _registry_with(["stt.new_source"])
        flow = WrappedEntityMissingRepairFlow(_entry())
        flow.hass = mock_hass

        result = await flow.async_step_init()
        assert result["type"] == "form"
        assert result["step_id"] == "init"
        assert (
            result["description_placeholders"]["wrapped_entity_id"] == "stt.gone_source"
        )

    @pytest.mark.asyncio
    async def test_first_call_with_issue_data_shows_form(self, mock_hass):
        """The repairs framework passes the ISSUE DATA dict (not None) on
        the first invocation — it must show the form, not KeyError
        (regression: 500 on opening the fix flow)."""
        _registry_with(["stt.new_source"])
        flow = WrappedEntityMissingRepairFlow(_entry())
        flow.hass = mock_hass

        result = await flow.async_step_init({"entry_id": "test_entry"})
        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_submit_rewires_entry_and_reloads(self, mock_hass):
        _registry_with(["stt.new_source"])
        mock_hass.states.get.return_value = MagicMock(
            attributes={"friendly_name": "New Source"}
        )
        entry = _entry()
        flow = WrappedEntityMissingRepairFlow(entry)
        flow.hass = mock_hass

        result = await flow.async_step_init({"wrapped_entity_id": "stt.new_source"})
        assert result["type"] == "create_entry"
        mock_hass.config_entries.async_update_entry.assert_called_once_with(
            entry,
            data={"wrapped_entity_id": "stt.new_source"},
            title="New Source Corrected",
            unique_id="stt.new_source",
        )
        mock_hass.config_entries.async_schedule_reload.assert_called_once_with(
            "entry-1"
        )


class TestAsyncCreateFixFlow:
    @pytest.mark.asyncio
    async def test_creates_flow_for_known_entry(self, mock_hass):
        entry = _entry()
        mock_hass.config_entries.async_get_entry.return_value = entry

        flow = await async_create_fix_flow(
            mock_hass,
            wrapped_entity_issue_id("entry-1"),
            {"entry_id": "entry-1"},
        )
        assert isinstance(flow, WrappedEntityMissingRepairFlow)

    @pytest.mark.asyncio
    async def test_raises_for_unknown_entry(self, mock_hass):
        mock_hass.config_entries.async_get_entry.return_value = None
        with pytest.raises(ValueError):
            await async_create_fix_flow(mock_hass, "bogus", {"entry_id": "nope"})


class TestIssueLifecycle:
    def _entity(self, mock_hass, wrapped="stt.gone_source"):
        from custom_components.stt_corrector.stt import CorrectedSTTEntity

        entry = _entry(wrapped=wrapped)
        entry.options = {}
        entry.runtime_data = MagicMock()
        return CorrectedSTTEntity(mock_hass, entry)

    def test_issue_created_when_wrapped_missing(self, mock_hass):
        import homeassistant.helpers.entity_registry as er
        import homeassistant.helpers.issue_registry as ir

        ent_reg = MagicMock()
        ent_reg.async_get.return_value = None  # wrapped entity gone
        er.async_get.return_value = ent_reg
        ir.async_create_issue.reset_mock()
        ir.async_delete_issue.reset_mock()

        entity = self._entity(mock_hass)
        entity._async_update_wrapped_entity_issue()

        ir.async_create_issue.assert_called_once()
        assert ir.async_create_issue.call_args.args[2] == wrapped_entity_issue_id(
            "entry-1"
        )
        ir.async_delete_issue.assert_not_called()

    def test_issue_cleared_when_wrapped_present(self, mock_hass):
        import homeassistant.helpers.entity_registry as er
        import homeassistant.helpers.issue_registry as ir

        ent_reg = MagicMock()
        ent_reg.async_get.return_value = _make_entity_entry("stt.gone_source")
        er.async_get.return_value = ent_reg
        ir.async_create_issue.reset_mock()
        ir.async_delete_issue.reset_mock()

        entity = self._entity(mock_hass)
        entity._async_update_wrapped_entity_issue()

        ir.async_create_issue.assert_not_called()
        ir.async_delete_issue.assert_called_once()

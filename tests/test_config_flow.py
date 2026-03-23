"""Tests for STT Corrector config flow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.stt_corrector.config_flow import (
    STTCorrectorConfigFlow,
    STTCorrectorOptionsFlow,
    _get_stt_entities,
)


def _make_entity_entry(
    entity_id: str,
    domain: str = "stt",
    platform: str = "azure_speech_stt",
    disabled_by: str | None = None,
    entry_id: str = "reg_id_1",
):
    return SimpleNamespace(
        entity_id=entity_id,
        domain=domain,
        platform=platform,
        disabled_by=disabled_by,
        id=entry_id,
    )


class TestGetSTTEntities:
    def test_returns_stt_entities(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        entries = [_make_entity_entry("stt.azure")]
        ent_reg.entities.values.return_value = entries
        er.async_get.return_value = ent_reg

        state = MagicMock()
        state.attributes = {"friendly_name": "Azure STT"}
        mock_hass.states.get.return_value = state

        options = _get_stt_entities(mock_hass)
        assert len(options) == 1
        assert options[0]["value"] == "stt.azure"

    def test_excludes_stt_corrector_entities(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        entries = [
            _make_entity_entry("stt.azure", platform="azure_speech_stt"),
            _make_entity_entry("stt.corrected", platform="stt_corrector"),
        ]
        ent_reg.entities.values.return_value = entries
        er.async_get.return_value = ent_reg

        mock_hass.states.get.return_value = MagicMock(
            attributes={"friendly_name": "Test"}
        )

        options = _get_stt_entities(mock_hass)
        assert len(options) == 1
        assert options[0]["value"] == "stt.azure"

    def test_excludes_disabled_entities(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        entries = [_make_entity_entry("stt.disabled", disabled_by="user")]
        ent_reg.entities.values.return_value = entries
        er.async_get.return_value = ent_reg

        options = _get_stt_entities(mock_hass)
        assert len(options) == 0

    def test_excludes_non_stt_entities(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        entries = [_make_entity_entry("light.living_room", domain="light")]
        ent_reg.entities.values.return_value = entries
        er.async_get.return_value = ent_reg

        options = _get_stt_entities(mock_hass)
        assert len(options) == 0


class TestConfigFlowUser:
    @pytest.mark.asyncio
    async def test_shows_form(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        entries = [_make_entity_entry("stt.azure")]
        ent_reg.entities.values.return_value = entries
        er.async_get.return_value = ent_reg

        mock_hass.states.get.return_value = MagicMock(
            attributes={"friendly_name": "Azure STT"}
        )

        flow = STTCorrectorConfigFlow()
        flow.hass = mock_hass
        result = await flow.async_step_user()
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_creates_entry(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        entity_entry = _make_entity_entry("stt.azure")
        ent_reg.entities.values.return_value = [entity_entry]
        ent_reg.async_get.return_value = entity_entry
        er.async_get.return_value = ent_reg

        mock_hass.states.get.return_value = MagicMock(
            attributes={"friendly_name": "Azure STT"}
        )

        flow = STTCorrectorConfigFlow()
        flow.hass = mock_hass
        result = await flow.async_step_user({"wrapped_entity_id": "stt.azure"})
        assert result["type"] == "create_entry"
        assert result["data"]["wrapped_entity_id"] == "stt.azure"
        assert "Corrected" in result["title"]

    @pytest.mark.asyncio
    async def test_aborts_when_no_stt_entities(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        ent_reg.entities.values.return_value = []
        er.async_get.return_value = ent_reg

        flow = STTCorrectorConfigFlow()
        flow.hass = mock_hass
        result = await flow.async_step_user()
        assert result["type"] == "abort"
        assert result["reason"] == "no_stt_entities"


class TestOptionsFlow:
    @pytest.mark.asyncio
    async def test_shows_form(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_init()
        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_saves_correction_settings(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_init(
            {
                "correction_stages": ["replacements", "similarity"],
                "auto_collect": {
                    "auto_collect_sources": ["areas", "entities"],
                    "custom_phrases": ["hello"],
                },
                "replacements": {
                    "custom_replacements": ["wrong=right"],
                },
                "similarity": {
                    "fuzzy_threshold": 0.85,
                    "custom_exclusions": ["ignore"],
                },
            }
        )
        assert result["type"] == "create_entry"
        data = result["data"]
        assert data["enable_custom_replacements"] is True
        assert data["enable_fuzzy_matching"] is True
        assert data["fuzzy_threshold"] == 0.85
        assert data["custom_phrases"] == ["hello"]
        assert data["custom_replacements"] == {"wrong": "right"}
        assert data["custom_exclusions"] == ["ignore"]

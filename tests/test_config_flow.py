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


class TestOptionsFlowMenu:
    """Tests for menu-based options flow."""

    @pytest.mark.asyncio
    async def test_init_shows_menu(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_init()
        assert result["type"] == "menu"
        assert "active_processors" in result["menu_options"]
        assert "language_settings" in result["menu_options"]
        assert "phrase_collection" in result["menu_options"]
        assert "replacements" in result["menu_options"]
        assert "similarity" in result["menu_options"]

    @pytest.mark.asyncio
    async def test_active_processors_shows_form(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_active_processors()
        assert result["type"] == "form"
        assert result["step_id"] == "active_processors"

    @pytest.mark.asyncio
    async def test_active_processors_saves(self):
        entry = MagicMock()
        entry.options = {"active_processors": ["replacements", "similarity"]}
        flow = STTCorrectorOptionsFlow(entry)
        flow.hass = MagicMock()
        result = await flow.async_step_active_processors(
            {
                "active_processors": [
                    "language_processing",
                    "replacements",
                    "similarity",
                ]
            }
        )
        assert result["type"] == "menu"
        saved = flow.hass.config_entries.async_update_entry.call_args[1]["options"]
        assert set(saved["active_processors"]) == {
            "language_processing",
            "replacements",
            "similarity",
        }

    @pytest.mark.asyncio
    async def test_active_processors_disable(self):
        """Deselecting a processor should save only the selected processors."""
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        flow.hass = MagicMock()
        result = await flow.async_step_active_processors(
            {"active_processors": ["replacements"]}
        )
        assert result["type"] == "menu"
        saved = flow.hass.config_entries.async_update_entry.call_args[1]["options"]
        assert saved["active_processors"] == ["replacements"]

    @pytest.mark.asyncio
    async def test_language_settings_shows_menu(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_language_settings()
        assert result["type"] == "menu"
        assert "lang_mandarin" in result["menu_options"]

    @pytest.mark.asyncio
    async def test_language_settings_has_back(self):
        """Language settings sub-menu should have a back option."""
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_language_settings()
        assert "init" in result["menu_options"]

    @pytest.mark.asyncio
    async def test_lang_mandarin_shows_form(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_lang_mandarin()
        assert result["type"] == "form"
        assert result["step_id"] == "lang_mandarin"

    @pytest.mark.asyncio
    async def test_lang_mandarin_saves(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        flow.hass = MagicMock()
        result = await flow.async_step_lang_mandarin(
            {
                "zh_tw": {
                    "strip_trailing_punctuation": True,
                    "trailing_punctuation": "。",
                    "script_conversion": "s2tw",
                    "pinyin_matching": True,
                },
                "zh_hk": {
                    "strip_trailing_punctuation": True,
                    "trailing_punctuation": "。",
                    "script_conversion": "",
                    "pinyin_matching": True,
                },
                "zh_cn": {
                    "strip_trailing_punctuation": False,
                    "trailing_punctuation": "。",
                    "script_conversion": "t2s",
                    "pinyin_matching": False,
                },
            }
        )
        assert result["type"] == "menu"
        saved = flow.hass.config_entries.async_update_entry.call_args[1]["options"]
        lang_cfg = saved["language_config"]["mandarin"]
        assert lang_cfg["zh-tw"]["script_conversion"] == "s2tw"
        assert lang_cfg["zh-tw"]["strip_trailing_punctuation"] is True
        assert lang_cfg["zh-hk"]["script_conversion"] == ""
        assert lang_cfg["zh-cn"]["script_conversion"] == "t2s"
        assert lang_cfg["zh-cn"]["pinyin_matching"] is False
        assert lang_cfg["zh-cn"]["strip_trailing_punctuation"] is False

    @pytest.mark.asyncio
    async def test_phrase_collection_shows_form(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_phrase_collection()
        assert result["type"] == "form"
        assert result["step_id"] == "phrase_collection"

    @pytest.mark.asyncio
    async def test_phrase_collection_saves(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        flow.hass = MagicMock()
        result = await flow.async_step_phrase_collection(
            {
                "auto_collect_sources": ["areas", "entities"],
                "custom_phrases": ["hello", "  world  "],
            }
        )
        assert result["type"] == "menu"
        saved = flow.hass.config_entries.async_update_entry.call_args[1]["options"]
        assert saved["auto_collect_sources"] == ["areas", "entities"]
        assert saved["custom_phrases"] == ["hello", "world"]

    @pytest.mark.asyncio
    async def test_replacements_shows_form(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_replacements()
        assert result["type"] == "form"
        assert result["step_id"] == "replacements"

    @pytest.mark.asyncio
    async def test_replacements_saves(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        flow.hass = MagicMock()
        result = await flow.async_step_replacements(
            {"custom_replacements": ["wrong=right", "bad=good"]}
        )
        assert result["type"] == "menu"
        saved = flow.hass.config_entries.async_update_entry.call_args[1]["options"]
        assert saved["custom_replacements"] == {"wrong": "right", "bad": "good"}

    @pytest.mark.asyncio
    async def test_similarity_shows_form(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        result = await flow.async_step_similarity()
        assert result["type"] == "form"
        assert result["step_id"] == "similarity"

    @pytest.mark.asyncio
    async def test_similarity_saves(self):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        flow.hass = MagicMock()
        result = await flow.async_step_similarity(
            {"fuzzy_threshold": 0.9, "custom_exclusions": ["ignore"]}
        )
        assert result["type"] == "menu"
        saved = flow.hass.config_entries.async_update_entry.call_args[1]["options"]
        assert saved["fuzzy_threshold"] == 0.9
        assert saved["custom_exclusions"] == ["ignore"]

    @pytest.mark.asyncio
    async def test_config_flow_version_is_1(self):
        """Config flow version should be 1."""
        assert STTCorrectorConfigFlow.VERSION == 1

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
    async def test_lang_mandarin_shows_form(self, mock_hass):
        entry = MagicMock()
        entry.options = {}
        flow = STTCorrectorOptionsFlow(entry)
        flow.hass = mock_hass
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


class TestOptionsFlowSttLanguageDropdown:
    """Test stt_language dropdown in language settings."""

    @pytest.mark.asyncio
    async def test_lang_mandarin_saves_stt_language(self, mock_hass):
        """stt_language field is saved in per-locale config."""
        from unittest.mock import patch

        entry = MagicMock()
        entry.options = {}
        entry.data = {"wrapped_entity_id": "stt.fun_asr"}
        flow = STTCorrectorOptionsFlow(entry)
        flow.hass = mock_hass

        with patch(
            "custom_components.stt_corrector.config_flow._resolve_wrapped_stt_languages",
            return_value=["zh", "en-US"],
        ):
            result = await flow.async_step_lang_mandarin(
                {
                    "zh_tw": {
                        "stt_language": "zh",
                        "strip_trailing_punctuation": True,
                        "trailing_punctuation": "。",
                        "script_conversion": "s2tw",
                        "pinyin_matching": True,
                    },
                    "zh_hk": {
                        "stt_language": "zh",
                        "strip_trailing_punctuation": True,
                        "trailing_punctuation": "。",
                        "script_conversion": "s2hk",
                        "pinyin_matching": True,
                    },
                    "zh_cn": {
                        "stt_language": "",
                        "strip_trailing_punctuation": True,
                        "trailing_punctuation": "。",
                        "script_conversion": "",
                        "pinyin_matching": True,
                    },
                }
            )

        # Verify it saved and returned to menu
        assert result["type"] == "menu"
        saved = mock_hass.config_entries.async_update_entry.call_args
        saved_options = saved[1]["options"]
        assert (
            saved_options["language_config"]["mandarin"]["zh-tw"]["stt_language"]
            == "zh"
        )
        assert (
            saved_options["language_config"]["mandarin"]["zh-hk"]["stt_language"]
            == "zh"
        )
        assert (
            saved_options["language_config"]["mandarin"]["zh-cn"]["stt_language"] == ""
        )


class TestConfigFlowReconfigure:
    def _flow_with_entry(self, mock_hass, entry):
        flow = STTCorrectorConfigFlow()
        flow.hass = mock_hass
        flow._get_reconfigure_entry = MagicMock(return_value=entry)
        flow._async_current_entries = MagicMock(return_value=[entry])
        flow.async_update_reload_and_abort = MagicMock(
            return_value={"type": "abort", "reason": "reconfigure_successful"}
        )
        return flow

    @staticmethod
    def _entry(
        entry_id="entry-1", wrapped="stt.old_source", unique_id="stt.old_source"
    ):
        entry = MagicMock()
        entry.entry_id = entry_id
        entry.unique_id = unique_id
        entry.data = {"wrapped_entity_id": wrapped}
        return entry

    @pytest.mark.asyncio
    async def test_shows_form_with_current_source_default(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        ent_reg.entities.values.return_value = [_make_entity_entry("stt.new_source")]
        er.async_get.return_value = ent_reg

        flow = self._flow_with_entry(mock_hass, self._entry())
        result = await flow.async_step_reconfigure()
        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure"

    @pytest.mark.asyncio
    async def test_reconfigure_updates_entry_and_preserves_it(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        ent_reg.entities.values.return_value = [_make_entity_entry("stt.new_source")]
        er.async_get.return_value = ent_reg
        mock_hass.states.get.return_value = MagicMock(
            attributes={"friendly_name": "New Source"}
        )

        entry = self._entry()
        flow = self._flow_with_entry(mock_hass, entry)
        result = await flow.async_step_reconfigure(
            {"wrapped_entity_id": "stt.new_source"}
        )
        assert result["reason"] == "reconfigure_successful"
        flow.async_update_reload_and_abort.assert_called_once_with(
            entry,
            unique_id="stt.new_source",
            title="New Source Corrected",
            data={"wrapped_entity_id": "stt.new_source"},
        )

    @pytest.mark.asyncio
    async def test_reconfigure_aborts_when_another_entry_wraps_target(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        ent_reg.entities.values.return_value = [_make_entity_entry("stt.new_source")]
        er.async_get.return_value = ent_reg

        entry = self._entry()
        other = self._entry(
            entry_id="entry-2", wrapped="stt.new_source", unique_id="stt.new_source"
        )
        flow = self._flow_with_entry(mock_hass, entry)
        flow._async_current_entries = MagicMock(return_value=[entry, other])

        result = await flow.async_step_reconfigure(
            {"wrapped_entity_id": "stt.new_source"}
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"
        flow.async_update_reload_and_abort.assert_not_called()


class TestConfigFlowTemplate:
    def _flow(self, mock_hass, existing):
        flow = STTCorrectorConfigFlow()
        flow.hass = mock_hass
        flow._async_current_entries = MagicMock(return_value=existing)
        return flow

    @pytest.mark.asyncio
    async def test_create_with_template_copies_options(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        ent_reg.entities.values.return_value = [_make_entity_entry("stt.new_source")]
        er.async_get.return_value = ent_reg
        mock_hass.states.get.return_value = MagicMock(
            attributes={"friendly_name": "New Source"}
        )

        template = MagicMock()
        template.entry_id = "tpl-entry"
        template.title = "SenseVoice Small Corrected"
        template.options = {
            "fuzzy_threshold": 0.8,
            "custom_replacements": {"熒幕": "螢幕"},
        }
        mock_hass.config_entries.async_get_entry = MagicMock(return_value=template)

        flow = self._flow(mock_hass, [template])
        result = await flow.async_step_user(
            {"wrapped_entity_id": "stt.new_source", "copy_from": "tpl-entry"}
        )
        assert result["type"] == "create_entry"
        assert result["options"] == template.options
        assert result["options"] is not template.options

    @pytest.mark.asyncio
    async def test_create_without_template_starts_blank(self, mock_hass):
        import homeassistant.helpers.entity_registry as er

        ent_reg = MagicMock()
        ent_reg.entities.values.return_value = [_make_entity_entry("stt.new_source")]
        er.async_get.return_value = ent_reg
        mock_hass.states.get.return_value = MagicMock(
            attributes={"friendly_name": "New Source"}
        )

        flow = self._flow(mock_hass, [])
        result = await flow.async_step_user({"wrapped_entity_id": "stt.new_source"})
        assert result["type"] == "create_entry"
        assert result["options"] == {}

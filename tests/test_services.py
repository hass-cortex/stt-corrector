"""Tests for STT Corrector service handlers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.stt_corrector.models import STTCorrectorRuntimeData

ENTITY_ID = "stt.test_corrected"


def _make_service_call(data: dict) -> MagicMock:
    """Create a mock ServiceCall with the given data."""
    call = MagicMock()
    call.data = data
    return call


def _make_config_entry(options: dict | None = None) -> MagicMock:
    """Create a mock config entry with the given options."""
    entity = MagicMock()
    entity.entity_id = ENTITY_ID

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.options = options or {}
    runtime_data = STTCorrectorRuntimeData()
    runtime_data.entity = entity
    entry.runtime_data = runtime_data
    return entry


def _mock_hass_with_entry(mock_hass, entry):
    """Set up mock_hass with config_entries that return the given entry."""
    mock_hass.config_entries = MagicMock()
    mock_hass.config_entries.async_entries = MagicMock(return_value=[entry])
    mock_hass.config_entries.async_update_entry = MagicMock()
    return mock_hass


class TestRegisterServices:
    """Test service registration."""

    def test_register_services(self, mock_hass):
        """async_register_services should register all 10 services."""
        from custom_components.stt_corrector.services import (
            async_register_services,
        )

        async_register_services(mock_hass)

        registered = {
            call[0][1] for call in mock_hass.services.async_register.call_args_list
        }
        expected = {
            "add_phrases",
            "remove_phrases",
            "add_replacements",
            "remove_replacements",
            "get_correction_config",
            "set_correction_config",
            "test_correction",
            "add_exclusions",
            "remove_exclusions",
            "copy_correction_config",
        }
        assert registered == expected

    def test_no_transcribe_service(self, mock_hass):
        """transcribe service must NOT be registered (Azure-specific)."""
        from custom_components.stt_corrector.services import (
            async_register_services,
        )

        async_register_services(mock_hass)

        registered = {
            call[0][1] for call in mock_hass.services.async_register.call_args_list
        }
        assert "transcribe" not in registered


class TestTestCorrection:
    """Test test_correction service handler."""

    @pytest.mark.asyncio
    async def test_returns_diagnostic_result(self, mock_hass):
        """Should return corrected text, changes, and candidates."""
        from custom_components.stt_corrector.correction.corrector import (
            SpeechCorrector,
        )
        from custom_components.stt_corrector.correction.processors.similarity import (
            SimilarityProcessor,
        )
        from custom_components.stt_corrector.services import (
            async_handle_test_correction,
        )

        corrector = SpeechCorrector(
            [
                SimilarityProcessor(known_phrases=["走廊燈"], threshold=0.75),
            ]
        )

        async def _test_correction(text):
            corrector.update_phrases(["走廊燈"])
            return corrector.diagnose(text)

        entity = MagicMock()
        entity.async_test_correction = _test_correction

        call = _make_service_call({"entity_id": ENTITY_ID, "text": "走廊等"})

        with patch(
            "custom_components.stt_corrector.services._find_stt_entity",
            return_value=entity,
        ):
            result = await async_handle_test_correction(mock_hass, call)

        assert result["original"] == "走廊等"
        assert result["corrected"] == "走廊燈"
        assert len(result["changes"]) == 1
        assert result["changes"][0]["method"] == "fuzzy_match"
        assert isinstance(result["candidates"], list)

    @pytest.mark.asyncio
    async def test_empty_text_raises_error(self, mock_hass):
        """Empty text should raise ServiceValidationError."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.stt_corrector.services import (
            async_handle_test_correction,
        )

        call = _make_service_call({"entity_id": ENTITY_ID, "text": ""})
        with pytest.raises(ServiceValidationError, match="required"):
            await async_handle_test_correction(mock_hass, call)


class TestAddPhrases:
    """Test add_phrases service."""

    @pytest.mark.asyncio
    async def test_add_new_phrases(self, mock_hass):
        """Adding new phrases should append them to the list."""
        from custom_components.stt_corrector.services import (
            async_handle_add_phrases,
        )

        entry = _make_config_entry({"custom_phrases": ["existing"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "phrases": ["new1", "new2"]})
        await async_handle_add_phrases(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_phrases"] == ["existing", "new1", "new2"]

    @pytest.mark.asyncio
    async def test_add_duplicate_phrases_deduped(self, mock_hass):
        """Duplicate phrases should not be added twice."""
        from custom_components.stt_corrector.services import (
            async_handle_add_phrases,
        )

        entry = _make_config_entry({"custom_phrases": ["a", "b"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "phrases": ["b", "c"]})
        await async_handle_add_phrases(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_phrases"] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_add_empty_phrases_noop(self, mock_hass):
        """Empty phrases list should not trigger an update."""
        from custom_components.stt_corrector.services import (
            async_handle_add_phrases,
        )

        entry = _make_config_entry()
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "phrases": []})
        await async_handle_add_phrases(mock_hass, call)

        mock_hass.config_entries.async_update_entry.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_stripped(self, mock_hass):
        """Phrases should be stripped of leading/trailing whitespace."""
        from custom_components.stt_corrector.services import (
            async_handle_add_phrases,
        )

        entry = _make_config_entry({"custom_phrases": []})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call(
            {"entity_id": ENTITY_ID, "phrases": ["  hello  ", "  world  "]}
        )
        await async_handle_add_phrases(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_phrases"] == ["hello", "world"]

    @pytest.mark.asyncio
    async def test_empty_string_after_strip_ignored(self, mock_hass):
        """Whitespace-only phrases should be ignored after stripping."""
        from custom_components.stt_corrector.services import (
            async_handle_add_phrases,
        )

        entry = _make_config_entry({"custom_phrases": []})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "phrases": ["  ", "valid"]})
        await async_handle_add_phrases(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_phrases"] == ["valid"]


class TestRemovePhrases:
    """Test remove_phrases service."""

    @pytest.mark.asyncio
    async def test_remove_existing_phrases(self, mock_hass):
        """Removing existing phrases should filter them out."""
        from custom_components.stt_corrector.services import (
            async_handle_remove_phrases,
        )

        entry = _make_config_entry({"custom_phrases": ["a", "b", "c"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "phrases": ["b"]})
        await async_handle_remove_phrases(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_phrases"] == ["a", "c"]

    @pytest.mark.asyncio
    async def test_remove_nonexistent_phrases(self, mock_hass):
        """Removing phrases that don't exist should not error."""
        from custom_components.stt_corrector.services import (
            async_handle_remove_phrases,
        )

        entry = _make_config_entry({"custom_phrases": ["a"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "phrases": ["z"]})
        await async_handle_remove_phrases(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_phrases"] == ["a"]

    @pytest.mark.asyncio
    async def test_remove_empty_list_noop(self, mock_hass):
        """Empty remove list should not trigger an update."""
        from custom_components.stt_corrector.services import (
            async_handle_remove_phrases,
        )

        entry = _make_config_entry({"custom_phrases": ["a"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "phrases": []})
        await async_handle_remove_phrases(mock_hass, call)

        mock_hass.config_entries.async_update_entry.assert_not_called()


class TestAddReplacements:
    """Test add_replacements service."""

    @pytest.mark.asyncio
    async def test_add_new_replacements(self, mock_hass):
        """Adding new replacement rules should merge them."""
        from custom_components.stt_corrector.services import (
            async_handle_add_replacements,
        )

        entry = _make_config_entry({"custom_replacements": {"a": "b"}})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "replacements": {"c": "d"}})
        await async_handle_add_replacements(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_replacements"] == {"a": "b", "c": "d"}

    @pytest.mark.asyncio
    async def test_update_existing_replacement(self, mock_hass):
        """Updating an existing key should overwrite the value."""
        from custom_components.stt_corrector.services import (
            async_handle_add_replacements,
        )

        entry = _make_config_entry({"custom_replacements": {"old": "v1"}})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call(
            {"entity_id": ENTITY_ID, "replacements": {"old": "v2"}}
        )
        await async_handle_add_replacements(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_replacements"] == {"old": "v2"}

    @pytest.mark.asyncio
    async def test_add_empty_replacements_noop(self, mock_hass):
        """Empty replacements dict should not trigger an update."""
        from custom_components.stt_corrector.services import (
            async_handle_add_replacements,
        )

        entry = _make_config_entry()
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "replacements": {}})
        await async_handle_add_replacements(mock_hass, call)

        mock_hass.config_entries.async_update_entry.assert_not_called()


class TestRemoveReplacements:
    """Test remove_replacements service."""

    @pytest.mark.asyncio
    async def test_remove_existing_keys(self, mock_hass):
        """Removing existing keys should delete them."""
        from custom_components.stt_corrector.services import (
            async_handle_remove_replacements,
        )

        entry = _make_config_entry({"custom_replacements": {"a": "1", "b": "2"}})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "keys": ["a"]})
        await async_handle_remove_replacements(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_replacements"] == {"b": "2"}

    @pytest.mark.asyncio
    async def test_remove_nonexistent_keys(self, mock_hass):
        """Removing keys that don't exist should not error."""
        from custom_components.stt_corrector.services import (
            async_handle_remove_replacements,
        )

        entry = _make_config_entry({"custom_replacements": {"a": "1"}})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "keys": ["z"]})
        await async_handle_remove_replacements(mock_hass, call)

        updated_options = mock_hass.config_entries.async_update_entry.call_args[1][
            "options"
        ]
        assert updated_options["custom_replacements"] == {"a": "1"}

    @pytest.mark.asyncio
    async def test_remove_empty_keys_noop(self, mock_hass):
        """Empty keys list should not trigger an update."""
        from custom_components.stt_corrector.services import (
            async_handle_remove_replacements,
        )

        entry = _make_config_entry()
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "keys": []})
        await async_handle_remove_replacements(mock_hass, call)

        mock_hass.config_entries.async_update_entry.assert_not_called()


class TestGetCorrectionConfig:
    """Test get_correction_config service."""

    @pytest.mark.asyncio
    async def test_returns_full_config(self, mock_hass):
        """Should return all correction-related options."""
        from custom_components.stt_corrector.services import (
            async_handle_get_correction_config,
        )

        entry = _make_config_entry(
            {
                "custom_phrases": ["phrase1"],
                "custom_replacements": {"a": "b"},
                "active_processors": [
                    "language_processing",
                    "replacements",
                ],
                "fuzzy_threshold": 0.9,
                "custom_exclusions": ["skip_this"],
            }
        )
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID})
        result = await async_handle_get_correction_config(mock_hass, call)

        assert result["custom_phrases"] == ["phrase1"]
        assert result["custom_replacements"] == {"a": "b"}
        assert result["enable_custom_replacements"] is True
        assert result["enable_fuzzy_matching"] is False
        assert result["fuzzy_threshold"] == 0.9
        assert result["custom_exclusions"] == ["skip_this"]

    @pytest.mark.asyncio
    async def test_returns_defaults_when_empty(self, mock_hass):
        """Should return defaults when no options are set."""
        from custom_components.stt_corrector.services import (
            async_handle_get_correction_config,
        )

        entry = _make_config_entry({})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID})
        result = await async_handle_get_correction_config(mock_hass, call)

        assert result["custom_phrases"] == []
        assert result["custom_replacements"] == {}
        assert result["enable_custom_replacements"] is True
        assert result["enable_fuzzy_matching"] is True
        assert result["fuzzy_threshold"] == 0.80
        assert result["custom_exclusions"] == []


class TestSetCorrectionConfig:
    """Test set_correction_config service."""

    @pytest.mark.asyncio
    async def test_set_full_config(self, mock_hass):
        """Setting all fields should update all options."""
        from custom_components.stt_corrector.services import (
            async_handle_set_correction_config,
        )

        entry = _make_config_entry({})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call(
            {
                "entity_id": ENTITY_ID,
                "custom_phrases": ["a", "b"],
                "custom_replacements": {"x": "y"},
                "enable_custom_replacements": False,
                "enable_fuzzy_matching": False,
                "fuzzy_threshold": 0.6,
                "custom_exclusions": ["skip"],
            }
        )
        await async_handle_set_correction_config(mock_hass, call)

        updated = mock_hass.config_entries.async_update_entry.call_args[1]["options"]
        assert updated["custom_phrases"] == ["a", "b"]
        assert updated["custom_replacements"] == {"x": "y"}
        assert "replacements" not in updated["active_processors"]
        assert "similarity" not in updated["active_processors"]
        assert updated["fuzzy_threshold"] == 0.6
        assert updated["custom_exclusions"] == ["skip"]

    @pytest.mark.asyncio
    async def test_set_partial_config(self, mock_hass):
        """Setting partial fields should only update those fields."""
        from custom_components.stt_corrector.services import (
            async_handle_set_correction_config,
        )

        entry = _make_config_entry(
            {
                "custom_phrases": ["existing"],
                "custom_replacements": {"old": "val"},
                "fuzzy_threshold": 0.8,
            }
        )
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "custom_phrases": ["new"]})
        await async_handle_set_correction_config(mock_hass, call)

        updated = mock_hass.config_entries.async_update_entry.call_args[1]["options"]
        assert updated["custom_phrases"] == ["new"]
        assert updated["custom_replacements"] == {"old": "val"}
        assert updated["fuzzy_threshold"] == 0.8


class TestAddExclusions:
    """Test add_exclusions service."""

    @pytest.mark.asyncio
    async def test_add_new_exclusions(self, mock_hass):
        """Adding new exclusions should append them."""
        from custom_components.stt_corrector.services import (
            async_handle_add_exclusions,
        )

        entry = _make_config_entry({"custom_exclusions": ["existing"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call(
            {"entity_id": ENTITY_ID, "exclusions": ["new1", "new2"]}
        )
        await async_handle_add_exclusions(mock_hass, call)

        updated = mock_hass.config_entries.async_update_entry.call_args[1]["options"]
        assert updated["custom_exclusions"] == ["existing", "new1", "new2"]

    @pytest.mark.asyncio
    async def test_add_duplicate_exclusions_deduped(self, mock_hass):
        """Duplicate exclusions should not be added twice."""
        from custom_components.stt_corrector.services import (
            async_handle_add_exclusions,
        )

        entry = _make_config_entry({"custom_exclusions": ["a"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "exclusions": ["a", "b"]})
        await async_handle_add_exclusions(mock_hass, call)

        updated = mock_hass.config_entries.async_update_entry.call_args[1]["options"]
        assert updated["custom_exclusions"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_add_empty_exclusions_noop(self, mock_hass):
        """Empty exclusions list should not trigger an update."""
        from custom_components.stt_corrector.services import (
            async_handle_add_exclusions,
        )

        entry = _make_config_entry()
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "exclusions": []})
        await async_handle_add_exclusions(mock_hass, call)

        mock_hass.config_entries.async_update_entry.assert_not_called()


class TestRemoveExclusions:
    """Test remove_exclusions service."""

    @pytest.mark.asyncio
    async def test_remove_existing_exclusions(self, mock_hass):
        """Removing existing exclusions should filter them out."""
        from custom_components.stt_corrector.services import (
            async_handle_remove_exclusions,
        )

        entry = _make_config_entry({"custom_exclusions": ["a", "b", "c"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "exclusions": ["b"]})
        await async_handle_remove_exclusions(mock_hass, call)

        updated = mock_hass.config_entries.async_update_entry.call_args[1]["options"]
        assert updated["custom_exclusions"] == ["a", "c"]

    @pytest.mark.asyncio
    async def test_remove_nonexistent_exclusions(self, mock_hass):
        """Removing exclusions that don't exist should not error."""
        from custom_components.stt_corrector.services import (
            async_handle_remove_exclusions,
        )

        entry = _make_config_entry({"custom_exclusions": ["a"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "exclusions": ["z"]})
        await async_handle_remove_exclusions(mock_hass, call)

        updated = mock_hass.config_entries.async_update_entry.call_args[1]["options"]
        assert updated["custom_exclusions"] == ["a"]

    @pytest.mark.asyncio
    async def test_remove_empty_exclusions_noop(self, mock_hass):
        """Empty remove list should not trigger an update."""
        from custom_components.stt_corrector.services import (
            async_handle_remove_exclusions,
        )

        entry = _make_config_entry({"custom_exclusions": ["a"]})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "exclusions": []})
        await async_handle_remove_exclusions(mock_hass, call)

        mock_hass.config_entries.async_update_entry.assert_not_called()


class TestSchemaValidation:
    """Test voluptuous schema validation on service inputs."""

    def test_set_correction_config_fuzzy_threshold_out_of_range(self):
        """Fuzzy threshold outside 0.5-1.0 should be rejected."""
        from custom_components.stt_corrector.services import (
            SCHEMA_SET_CORRECTION_CONFIG,
        )

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_SET_CORRECTION_CONFIG(
                {"entity_id": ENTITY_ID, "fuzzy_threshold": 0.1}
            )

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_SET_CORRECTION_CONFIG(
                {"entity_id": ENTITY_ID, "fuzzy_threshold": 1.5}
            )

    def test_set_correction_config_valid_threshold(self):
        """Valid fuzzy threshold should be accepted."""
        from custom_components.stt_corrector.services import (
            SCHEMA_SET_CORRECTION_CONFIG,
        )

        result = SCHEMA_SET_CORRECTION_CONFIG(
            {"entity_id": ENTITY_ID, "fuzzy_threshold": 0.75}
        )
        assert result["fuzzy_threshold"] == 0.75

    def test_phrases_schema_rejects_non_list(self):
        """Non-list phrases should be rejected."""
        from custom_components.stt_corrector.services import SCHEMA_PHRASES

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_PHRASES({"entity_id": ENTITY_ID, "phrases": "not-a-list"})

    def test_add_replacements_schema_rejects_non_dict(self):
        """Non-dict replacements should be rejected."""
        from custom_components.stt_corrector.services import (
            SCHEMA_ADD_REPLACEMENTS,
        )

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_ADD_REPLACEMENTS(
                {"entity_id": ENTITY_ID, "replacements": "not-a-dict"}
            )

    def test_test_correction_schema_requires_text(self):
        """Missing text field should be rejected."""
        from custom_components.stt_corrector.services import (
            SCHEMA_TEST_CORRECTION,
        )

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_TEST_CORRECTION({"entity_id": ENTITY_ID})

    def test_exclusions_schema_rejects_non_list(self):
        """Non-list exclusions should be rejected."""
        from custom_components.stt_corrector.services import SCHEMA_EXCLUSIONS

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_EXCLUSIONS({"entity_id": ENTITY_ID, "exclusions": "not-a-list"})

    def test_remove_replacements_schema_rejects_non_list(self):
        """Non-list keys should be rejected."""
        from custom_components.stt_corrector.services import (
            SCHEMA_REMOVE_REPLACEMENTS,
        )

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_REMOVE_REPLACEMENTS({"entity_id": ENTITY_ID, "keys": "not-a-list"})

    def test_schemas_reject_missing_entity_id(self):
        """All schemas should reject missing entity_id."""
        from custom_components.stt_corrector.services import (
            SCHEMA_EXCLUSIONS,
            SCHEMA_GET_CORRECTION_CONFIG,
            SCHEMA_PHRASES,
            SCHEMA_SET_CORRECTION_CONFIG,
            SCHEMA_TEST_CORRECTION,
        )

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_GET_CORRECTION_CONFIG({})

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_PHRASES({"phrases": ["test"]})

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_TEST_CORRECTION({"text": "hello"})

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_SET_CORRECTION_CONFIG({"fuzzy_threshold": 0.75})

        with pytest.raises(vol.MultipleInvalid):
            SCHEMA_EXCLUSIONS({"exclusions": ["test"]})


class TestInputLimits:
    """Test input size limits."""

    @pytest.mark.asyncio
    async def test_add_phrases_exceeds_limit(self, mock_hass):
        """Adding phrases beyond MAX_PHRASE_LIST_SIZE should be rejected."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.stt_corrector.services import (
            MAX_PHRASE_LIST_SIZE,
            async_handle_add_phrases,
        )

        entry = _make_config_entry(
            {"custom_phrases": [f"phrase_{i}" for i in range(MAX_PHRASE_LIST_SIZE)]}
        )
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call({"entity_id": ENTITY_ID, "phrases": ["one_more"]})
        with pytest.raises(ServiceValidationError, match="maximum size"):
            await async_handle_add_phrases(mock_hass, call)

    @pytest.mark.asyncio
    async def test_add_replacements_exceeds_limit(self, mock_hass):
        """Adding replacements beyond MAX_REPLACEMENT_RULES should be rejected."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.stt_corrector.services import (
            MAX_REPLACEMENT_RULES,
            async_handle_add_replacements,
        )

        existing = {f"key_{i}": f"val_{i}" for i in range(MAX_REPLACEMENT_RULES)}
        entry = _make_config_entry({"custom_replacements": existing})
        _mock_hass_with_entry(mock_hass, entry)

        call = _make_service_call(
            {"entity_id": ENTITY_ID, "replacements": {"new_key": "new_val"}}
        )
        with pytest.raises(ServiceValidationError, match="maximum"):
            await async_handle_add_replacements(mock_hass, call)

    @pytest.mark.asyncio
    async def test_set_correction_config_replacements_exceeds_limit(self, mock_hass):
        """Setting too many replacement rules should be rejected."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.stt_corrector.services import (
            MAX_REPLACEMENT_RULES,
            async_handle_set_correction_config,
        )

        entry = _make_config_entry({})
        _mock_hass_with_entry(mock_hass, entry)

        too_many = {f"k{i}": f"v{i}" for i in range(MAX_REPLACEMENT_RULES + 1)}
        call = _make_service_call(
            {"entity_id": ENTITY_ID, "custom_replacements": too_many}
        )
        with pytest.raises(ServiceValidationError, match="maximum"):
            await async_handle_set_correction_config(mock_hass, call)

    @pytest.mark.asyncio
    async def test_set_correction_config_phrases_exceeds_limit(self, mock_hass):
        """Setting too many phrases should be rejected."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.stt_corrector.services import (
            MAX_PHRASE_LIST_SIZE,
            async_handle_set_correction_config,
        )

        entry = _make_config_entry({})
        _mock_hass_with_entry(mock_hass, entry)

        too_many = [f"p{i}" for i in range(MAX_PHRASE_LIST_SIZE + 1)]
        call = _make_service_call({"entity_id": ENTITY_ID, "custom_phrases": too_many})
        with pytest.raises(ServiceValidationError, match="maximum"):
            await async_handle_set_correction_config(mock_hass, call)


class TestNoConfigEntry:
    """Test error handling when no config entry is found."""

    @pytest.mark.asyncio
    async def test_add_phrases_no_entry_raises(self, mock_hass):
        """Should raise ServiceValidationError when no config entry exists."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.stt_corrector.services import (
            async_handle_add_phrases,
        )

        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_entries = MagicMock(return_value=[])

        call = _make_service_call({"entity_id": ENTITY_ID, "phrases": ["test"]})
        with pytest.raises(ServiceValidationError, match="config entry"):
            await async_handle_add_phrases(mock_hass, call)

    @pytest.mark.asyncio
    async def test_get_config_no_entry_raises(self, mock_hass):
        """Should raise ServiceValidationError when no config entry exists."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.stt_corrector.services import (
            async_handle_get_correction_config,
        )

        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_entries = MagicMock(return_value=[])

        call = _make_service_call({"entity_id": ENTITY_ID})
        with pytest.raises(ServiceValidationError, match="config entry"):
            await async_handle_get_correction_config(mock_hass, call)


class TestNoSTTEntity:
    """Test error handling when no STT entity is found."""

    @pytest.mark.asyncio
    async def test_test_correction_no_entity_raises(self, mock_hass):
        """Should raise ServiceValidationError when no matching STT entity exists."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.stt_corrector.services import (
            async_handle_test_correction,
        )

        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_entries = MagicMock(return_value=[])

        call = _make_service_call({"entity_id": ENTITY_ID, "text": "hello"})
        with pytest.raises(ServiceValidationError, match="STT entity"):
            await async_handle_test_correction(mock_hass, call)


class TestCopyCorrectionConfig:
    """Test copy_correction_config service."""

    def _entry_for(self, entity_id: str, options: dict) -> MagicMock:
        entry = _make_config_entry(options)
        entry.entry_id = f"entry_{entity_id}"
        entry.runtime_data.entity.entity_id = entity_id
        return entry

    def _hass_with_entries(self, mock_hass, entries):
        mock_hass.config_entries = MagicMock()
        mock_hass.config_entries.async_entries = MagicMock(return_value=entries)
        mock_hass.config_entries.async_update_entry = MagicMock()
        return mock_hass

    @pytest.mark.asyncio
    async def test_copy_to_multiple_targets(self, mock_hass):
        """Source options should replace every target's options."""
        from custom_components.stt_corrector.services import (
            async_handle_copy_correction_config,
        )

        source_options = {
            "custom_replacements": {"熒幕": "螢幕"},
            "fuzzy_threshold": 0.8,
        }
        source = self._entry_for("stt.source_corrected", source_options)
        target_a = self._entry_for("stt.a_corrected", {"fuzzy_threshold": 0.6})
        target_b = self._entry_for("stt.b_corrected", {})
        self._hass_with_entries(mock_hass, [source, target_a, target_b])

        call = _make_service_call(
            {
                "source_entity_id": "stt.source_corrected",
                "target_entity_id": ["stt.a_corrected", "stt.b_corrected"],
            }
        )
        await async_handle_copy_correction_config(mock_hass, call)

        calls = mock_hass.config_entries.async_update_entry.call_args_list
        assert len(calls) == 2
        assert {c[0][0].entry_id for c in calls} == {
            "entry_stt.a_corrected",
            "entry_stt.b_corrected",
        }
        for c in calls:
            assert c[1]["options"] == source_options
            # A copy, not a shared reference.
            assert c[1]["options"] is not source_options

    @pytest.mark.asyncio
    async def test_copy_accepts_single_target_string(self, mock_hass):
        """A bare string target should behave like a one-element list."""
        from custom_components.stt_corrector.services import (
            async_handle_copy_correction_config,
        )

        source = self._entry_for("stt.source_corrected", {"fuzzy_threshold": 0.9})
        target = self._entry_for("stt.a_corrected", {})
        self._hass_with_entries(mock_hass, [source, target])

        call = _make_service_call(
            {
                "source_entity_id": "stt.source_corrected",
                "target_entity_id": "stt.a_corrected",
            }
        )
        await async_handle_copy_correction_config(mock_hass, call)

        assert mock_hass.config_entries.async_update_entry.call_count == 1

    @pytest.mark.asyncio
    async def test_copy_rejects_source_as_target(self, mock_hass):
        """Copying an entry onto itself should raise."""
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.stt_corrector.services import (
            async_handle_copy_correction_config,
        )

        source = self._entry_for("stt.source_corrected", {})
        self._hass_with_entries(mock_hass, [source])

        call = _make_service_call(
            {
                "source_entity_id": "stt.source_corrected",
                "target_entity_id": ["stt.source_corrected"],
            }
        )
        with pytest.raises(ServiceValidationError):
            await async_handle_copy_correction_config(mock_hass, call)
        mock_hass.config_entries.async_update_entry.assert_not_called()

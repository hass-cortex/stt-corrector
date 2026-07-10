"""Tests for STT Corrector sensor platform."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.stt_corrector.models import (
    CorrectionStats,
    STTCorrectorRuntimeData,
)
from custom_components.stt_corrector.sensor import (
    SENSOR_DESCRIPTIONS,
    STTCorrectorSensor,
    STTCorrectorSensorDescription,
)

# ── Helpers ──


def _make_config_entry(entry_id: str = "test_entry_123") -> MagicMock:
    """Create a mock ConfigEntry with runtime_data."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.runtime_data = STTCorrectorRuntimeData()
    return entry


def _make_sensor(
    key: str,
    config_entry: MagicMock | None = None,
) -> STTCorrectorSensor:
    """Create a sensor for the given description key."""
    config_entry = config_entry or _make_config_entry()
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
    return STTCorrectorSensor(config_entry, desc)


def _success_stats(**kwargs) -> CorrectionStats:
    """Create a successful CorrectionStats."""
    defaults = {
        "result_state": "success",
        "correction_applied": False,
        "language": "en-US",
        "raw_text": "hello world",
        "corrected_text": "hello world",
    }
    defaults.update(kwargs)
    return CorrectionStats(**defaults)


def _no_speech_stats() -> CorrectionStats:
    return CorrectionStats(result_state="no_speech", language="en-US")


def _error_stats() -> CorrectionStats:
    return CorrectionStats(result_state="error", language="en-US")


def _wrapped_unavailable_stats() -> CorrectionStats:
    return CorrectionStats(result_state="wrapped_unavailable", language="en-US")


# ── Description Tests ──


class TestSensorDescriptions:
    """Verify sensor descriptions are correctly defined."""

    def test_expected_keys(self):
        keys = {d.key for d in SENSOR_DESCRIPTIONS}
        assert keys == {
            "total_requests",
            "successful_requests",
            "failed_requests",
            "corrections_applied",
            "last_raw_text",
            "last_corrected_text",
            "last_result",
            "last_language",
            "last_processing_time",
            "last_capture_device",
        }

    def test_no_azure_specific_sensors(self):
        """Verify Azure-specific sensors are NOT present."""
        keys = {d.key for d in SENSOR_DESCRIPTIONS}
        azure_only = {
            "last_duration",
            "average_duration",
            "last_audio_size",
            "total_audio_duration",
            "last_audio_duration",
            "last_api_used",
        }
        assert keys.isdisjoint(azure_only)

    def test_description_is_subclass(self):
        from homeassistant.components.sensor import SensorEntityDescription

        assert issubclass(STTCorrectorSensorDescription, SensorEntityDescription)

    def test_last_result_options(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "last_result")
        assert desc.options == [
            "success",
            "no_speech",
            "error",
            "wrapped_unavailable",
        ]

    def test_successful_requests_disabled_by_default(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "successful_requests")
        assert desc.entity_registry_enabled_default is False

    def test_last_language_disabled_by_default(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "last_language")
        assert desc.entity_registry_enabled_default is False


# ── Sensor Init Tests ──


class TestSensorInit:
    """Verify sensor initialization."""

    def test_unique_id_format(self):
        entry = _make_config_entry("abc123")
        sensor = _make_sensor("total_requests", entry)
        assert sensor._attr_unique_id == "stt_corrector_abc123_total_requests"

    def test_device_info_set(self):
        entry = _make_config_entry("abc123")
        sensor = _make_sensor("total_requests", entry)
        assert sensor._attr_device_info == {
            "identifiers": {("stt_corrector", "abc123")}
        }

    def test_has_entity_name(self):
        sensor = _make_sensor("total_requests")
        assert sensor.has_entity_name is True

    def test_should_not_poll(self):
        sensor = _make_sensor("total_requests")
        assert sensor._attr_should_poll is False


# ── Lifecycle Tests ──


class TestSensorLifecycle:
    """Verify async_added_to_hass / async_will_remove_from_hass."""

    @pytest.mark.asyncio
    async def test_registers_in_runtime_data_sensors(self):
        entry = _make_config_entry()
        sensor = _make_sensor("total_requests", entry)
        await sensor.async_added_to_hass()
        assert sensor in entry.runtime_data.sensors

    @pytest.mark.asyncio
    async def test_unregisters_on_remove(self):
        entry = _make_config_entry()
        sensor = _make_sensor("total_requests", entry)
        await sensor.async_added_to_hass()
        assert sensor in entry.runtime_data.sensors
        await sensor.async_will_remove_from_hass()
        assert sensor not in entry.runtime_data.sensors

    @pytest.mark.asyncio
    async def test_remove_when_not_registered_does_not_raise(self):
        entry = _make_config_entry()
        sensor = _make_sensor("total_requests", entry)
        # Never added — should not raise
        await sensor.async_will_remove_from_hass()

    @pytest.mark.asyncio
    async def test_restores_previous_value(self):
        entry = _make_config_entry()
        sensor = _make_sensor("total_requests", entry)

        # Mock async_get_last_sensor_data to return a previous value
        last_data = SimpleNamespace(native_value=42)
        sensor.async_get_last_sensor_data = lambda: _async_return(last_data)

        await sensor.async_added_to_hass()
        assert sensor._attr_native_value == 42

    @pytest.mark.asyncio
    async def test_no_restore_when_no_previous_data(self):
        entry = _make_config_entry()
        sensor = _make_sensor("total_requests", entry)
        sensor.async_get_last_sensor_data = lambda: _async_return(None)
        await sensor.async_added_to_hass()
        assert sensor._attr_native_value is None

    @pytest.mark.asyncio
    async def test_no_restore_when_previous_value_is_none(self):
        entry = _make_config_entry()
        sensor = _make_sensor("total_requests", entry)
        last_data = SimpleNamespace(native_value=None)
        sensor.async_get_last_sensor_data = lambda: _async_return(last_data)
        await sensor.async_added_to_hass()
        assert sensor._attr_native_value is None


async def _async_return(value):
    """Helper to create an awaitable returning the given value."""
    return value


# ── update_fn Tests: Counters ──


class TestCounterSensors:
    """Verify counter sensor update_fn behavior."""

    def test_total_requests_increments_on_every_push(self):
        sensor = _make_sensor("total_requests")
        sensor.handle_transcription(_success_stats())
        assert sensor._attr_native_value == 1
        sensor.handle_transcription(_no_speech_stats())
        assert sensor._attr_native_value == 2
        sensor.handle_transcription(_error_stats())
        assert sensor._attr_native_value == 3
        sensor.handle_transcription(_wrapped_unavailable_stats())
        assert sensor._attr_native_value == 4

    def test_total_requests_from_restored_value(self):
        sensor = _make_sensor("total_requests")
        sensor._attr_native_value = 10
        sensor.handle_transcription(_success_stats())
        assert sensor._attr_native_value == 11

    def test_successful_requests_only_counts_success(self):
        sensor = _make_sensor("successful_requests")
        sensor.handle_transcription(_success_stats())
        assert sensor._attr_native_value == 1
        sensor.handle_transcription(_no_speech_stats())
        assert sensor._attr_native_value == 1  # unchanged
        sensor.handle_transcription(_error_stats())
        assert sensor._attr_native_value == 1  # unchanged
        sensor.handle_transcription(_success_stats())
        assert sensor._attr_native_value == 2

    def test_corrections_applied_only_counts_corrections(self):
        sensor = _make_sensor("corrections_applied")
        sensor.handle_transcription(_success_stats(correction_applied=False))
        # update_fn returns int(None or 0) + 0 = 0; 0 != None so value is set to 0
        assert sensor._attr_native_value == 0

    def test_corrections_applied_increments(self):
        sensor = _make_sensor("corrections_applied")
        sensor.handle_transcription(_success_stats(correction_applied=True))
        assert sensor._attr_native_value == 1
        sensor.handle_transcription(_success_stats(correction_applied=True))
        assert sensor._attr_native_value == 2
        sensor.handle_transcription(_success_stats(correction_applied=False))
        assert sensor._attr_native_value == 2  # unchanged

    def test_corrections_applied_counts_across_result_states(self):
        """correction_applied can be True even on non-success (edge case)."""
        sensor = _make_sensor("corrections_applied")
        sensor.handle_transcription(
            CorrectionStats(
                result_state="error", correction_applied=True, language="en-US"
            )
        )
        assert sensor._attr_native_value == 1


# ── update_fn Tests: Text Sensors ──


class TestTextSensors:
    """Verify text sensor update_fn behavior."""

    def test_last_raw_text_on_success(self):
        sensor = _make_sensor("last_raw_text")
        sensor.handle_transcription(_success_stats(raw_text="hello"))
        assert sensor._attr_native_value == "hello"

    def test_last_raw_text_clears_on_no_speech(self):
        sensor = _make_sensor("last_raw_text")
        sensor.handle_transcription(_success_stats(raw_text="hello"))
        assert sensor._attr_native_value == "hello"
        sensor.handle_transcription(_no_speech_stats())
        assert sensor._attr_native_value is None

    def test_last_raw_text_keeps_value_on_error(self):
        sensor = _make_sensor("last_raw_text")
        sensor.handle_transcription(_success_stats(raw_text="hello"))
        sensor.handle_transcription(_error_stats())
        assert sensor._attr_native_value == "hello"  # preserved

    def test_last_corrected_text_on_success(self):
        sensor = _make_sensor("last_corrected_text")
        sensor.handle_transcription(_success_stats(corrected_text="fixed text"))
        assert sensor._attr_native_value == "fixed text"

    def test_last_corrected_text_clears_on_no_speech(self):
        sensor = _make_sensor("last_corrected_text")
        sensor.handle_transcription(_success_stats(corrected_text="fixed"))
        sensor.handle_transcription(_no_speech_stats())
        assert sensor._attr_native_value is None

    def test_last_corrected_text_keeps_value_on_error(self):
        sensor = _make_sensor("last_corrected_text")
        sensor.handle_transcription(_success_stats(corrected_text="fixed"))
        sensor.handle_transcription(_error_stats())
        assert sensor._attr_native_value == "fixed"  # preserved

    def test_last_corrected_text_clears_on_wrapped_unavailable(self):
        sensor = _make_sensor("last_corrected_text")
        sensor.handle_transcription(_success_stats(corrected_text="fixed"))
        sensor.handle_transcription(_wrapped_unavailable_stats())
        assert sensor._attr_native_value is None


# ── update_fn Tests: Enum/Metadata Sensors ──


class TestEnumSensors:
    """Verify enum and metadata sensor update_fn behavior."""

    def test_last_result_success(self):
        sensor = _make_sensor("last_result")
        sensor.handle_transcription(_success_stats())
        assert sensor._attr_native_value == "success"

    def test_last_result_no_speech(self):
        sensor = _make_sensor("last_result")
        sensor.handle_transcription(_no_speech_stats())
        assert sensor._attr_native_value == "no_speech"

    def test_last_result_error(self):
        sensor = _make_sensor("last_result")
        sensor.handle_transcription(_error_stats())
        assert sensor._attr_native_value == "error"

    def test_last_result_wrapped_unavailable(self):
        sensor = _make_sensor("last_result")
        sensor.handle_transcription(_wrapped_unavailable_stats())
        assert sensor._attr_native_value == "wrapped_unavailable"

    def test_last_language_updates(self):
        sensor = _make_sensor("last_language")
        sensor.handle_transcription(_success_stats(language="zh-TW"))
        assert sensor._attr_native_value == "zh-TW"
        sensor.handle_transcription(_success_stats(language="en-US"))
        assert sensor._attr_native_value == "en-US"

    def test_last_language_updates_on_all_result_states(self):
        sensor = _make_sensor("last_language")
        sensor.handle_transcription(_error_stats())
        assert sensor._attr_native_value == "en-US"


# ── handle_transcription State Write Tests ──


class TestHandleTranscription:
    """Verify handle_transcription calls async_write_ha_state correctly."""

    def test_writes_state_on_change(self):
        sensor = _make_sensor("total_requests")
        sensor.async_write_ha_state = MagicMock()
        sensor.handle_transcription(_success_stats())
        sensor.async_write_ha_state.assert_called_once()

    def test_does_not_write_state_when_unchanged(self):
        sensor = _make_sensor("successful_requests")
        sensor._attr_native_value = 5
        sensor.async_write_ha_state = MagicMock()
        # no_speech does not increment successful_requests — value stays 5
        sensor.handle_transcription(_no_speech_stats())
        sensor.async_write_ha_state.assert_not_called()


# ── async_setup_entry Tests ──


class TestAsyncSetupEntry:
    """Verify platform setup function."""

    @pytest.mark.asyncio
    async def test_creates_all_sensors(self):
        from custom_components.stt_corrector.sensor import async_setup_entry

        entry = _make_config_entry()
        added_entities: list = []

        def async_add_entities(entities):
            added_entities.extend(entities)

        await async_setup_entry(MagicMock(), entry, async_add_entities)

        keys = {e.entity_description.key for e in added_entities}
        assert keys == {
            "total_requests",
            "successful_requests",
            "failed_requests",
            "corrections_applied",
            "last_raw_text",
            "last_corrected_text",
            "last_result",
            "last_language",
            "last_processing_time",
            "last_capture_device",
        }

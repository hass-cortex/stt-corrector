"""Sensor platform for STT Corrector runtime statistics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .models import CorrectionStats, STTCorrectorRuntimeData

if TYPE_CHECKING:
    from . import STTCorrectorConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class STTCorrectorSensorDescription(SensorEntityDescription):
    """Describe an STT Corrector sensor."""

    update_fn: Callable[[Any, CorrectionStats], Any] = lambda cur, s: cur


SENSOR_DESCRIPTIONS: tuple[STTCorrectorSensorDescription, ...] = (
    STTCorrectorSensorDescription(
        key="total_requests",
        translation_key="total_requests",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_fn=lambda cur, s: int(cur or 0) + 1,
    ),
    STTCorrectorSensorDescription(
        key="successful_requests",
        translation_key="successful_requests",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        update_fn=lambda cur, s: (
            int(cur or 0) + (1 if s.result_state == "success" else 0)
        ),
    ),
    STTCorrectorSensorDescription(
        key="failed_requests",
        translation_key="failed_requests",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_fn=lambda cur, s: (
            int(cur or 0)
            + (1 if s.result_state in ("error", "wrapped_unavailable") else 0)
        ),
    ),
    STTCorrectorSensorDescription(
        key="corrections_applied",
        translation_key="corrections_applied",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_fn=lambda cur, s: int(cur or 0) + (1 if s.correction_applied else 0),
    ),
    STTCorrectorSensorDescription(
        key="last_raw_text",
        translation_key="last_raw_text",
        update_fn=lambda cur, s: (
            s.raw_text
            if s.result_state == "success"
            else (None if s.result_state != "error" else cur)
        ),
    ),
    STTCorrectorSensorDescription(
        key="last_corrected_text",
        translation_key="last_corrected_text",
        update_fn=lambda cur, s: (
            s.corrected_text
            if s.result_state == "success"
            else (None if s.result_state != "error" else cur)
        ),
    ),
    STTCorrectorSensorDescription(
        key="last_result",
        translation_key="last_result",
        entity_category=EntityCategory.DIAGNOSTIC,
        options=["success", "no_speech", "error", "wrapped_unavailable"],
        device_class=SensorDeviceClass.ENUM,
        update_fn=lambda cur, s: s.result_state,
    ),
    STTCorrectorSensorDescription(
        key="last_language",
        translation_key="last_language",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        update_fn=lambda cur, s: s.language,
    ),
    STTCorrectorSensorDescription(
        key="last_processing_time",
        translation_key="last_processing_time",
        native_unit_of_measurement="ms",
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        update_fn=lambda cur, s: (
            s.processing_time_ms if s.processing_time_ms is not None else cur
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: STTCorrectorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up STT Corrector sensors from a config entry."""
    async_add_entities(
        STTCorrectorSensor(config_entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class STTCorrectorSensor(RestoreSensor):
    """Sensor that tracks STT correction statistics.

    Each sensor owns its value and persists it via RestoreSensor.
    The STT entity pushes CorrectionStats after each invocation,
    and each sensor updates itself via its description's update_fn.
    """

    has_entity_name = True
    entity_description: STTCorrectorSensorDescription
    _attr_should_poll = False

    def __init__(
        self,
        config_entry: STTCorrectorConfigEntry,
        description: STTCorrectorSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
        )

    async def async_added_to_hass(self) -> None:
        """Restore last state and register for updates from STT entity."""
        await super().async_added_to_hass()

        # Restore previous value from HA's built-in state restore
        last_data = await self.async_get_last_sensor_data()
        if last_data and last_data.native_value is not None:
            self._attr_native_value = last_data.native_value

        # Register for push updates from STT entity
        runtime_data: STTCorrectorRuntimeData = self._config_entry.runtime_data
        runtime_data.sensors.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this sensor."""
        runtime_data: STTCorrectorRuntimeData = self._config_entry.runtime_data
        try:
            runtime_data.sensors.remove(self)
        except ValueError:
            pass

    def handle_transcription(self, stats: CorrectionStats) -> None:
        """Update sensor value from correction statistics."""
        new_value = self.entity_description.update_fn(self._attr_native_value, stats)
        if new_value != self._attr_native_value:
            self._attr_native_value = new_value
            self.async_write_ha_state()

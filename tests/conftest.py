"""Test fixtures for stt-corrector.

Mocks the homeassistant module hierarchy so that custom_components
can be imported without real dependencies.
"""

import sys
from dataclasses import dataclass
from enum import StrEnum
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

# ── Mock homeassistant module hierarchy ──
_ha = ModuleType("homeassistant")
_ha_core = ModuleType("homeassistant.core")
_ha_config_entries = ModuleType("homeassistant.config_entries")
_ha_data_entry_flow = ModuleType("homeassistant.data_entry_flow")
_ha_helpers = ModuleType("homeassistant.helpers")
_ha_helpers_cv = ModuleType("homeassistant.helpers.config_validation")
_ha_helpers_cv.config_entry_only_config_schema = lambda domain: {}
_ha_helpers_er = ModuleType("homeassistant.helpers.entity_registry")
_ha_helpers_ar = ModuleType("homeassistant.helpers.area_registry")
_ha_helpers_dr = ModuleType("homeassistant.helpers.device_registry")
_ha_helpers_fr = ModuleType("homeassistant.helpers.floor_registry")
_ha_components = ModuleType("homeassistant.components")
_ha_components_ha = ModuleType("homeassistant.components.homeassistant")
_ha_components_ha_exposed = ModuleType(
    "homeassistant.components.homeassistant.exposed_entities"
)

# Exceptions
_ha_exceptions = ModuleType("homeassistant.exceptions")
_ha_exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
_ha_exceptions.ServiceValidationError = type(
    "ServiceValidationError",
    (_ha_exceptions.HomeAssistantError,),
    {"__init__": lambda self, *a, **kw: Exception.__init__(self, *a)},
)

# Core
_ha_core.HomeAssistant = MagicMock
_ha_core.callback = lambda f: f
_ha_core.Event = MagicMock
_ha_core.ServiceCall = MagicMock
_ha_core.SupportsResponse = MagicMock()
_ha_core.SupportsResponse.ONLY = "only"
_ha_core.SupportsResponse.OPTIONAL = "optional"
_ha_core.SupportsResponse.NONE = "none"
_ha_core.ServiceResponse = dict

# ── ConfigFlow / OptionsFlow base classes ──
# Provide real base classes so subclasses can be instantiated and tested.


class _MockConfigFlow:
    """Mock ConfigFlow base class."""

    VERSION = 1
    hass = None
    _unique_id = None

    def __init__(self):
        self.context = {}

    def __init_subclass__(cls, *, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}

    async def async_set_unique_id(self, unique_id):
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass

    @staticmethod
    def async_get_options_flow(config_entry):
        raise NotImplementedError


class _MockOptionsFlow:
    """Mock OptionsFlow base class."""

    hass = None
    config_entry = None

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    @staticmethod
    def add_suggested_values_to_schema(schema, suggested_values):
        return schema


# Config entries
_ha_config_entries.ConfigEntry = MagicMock
_ha_config_entries.ConfigFlow = _MockConfigFlow
_ha_config_entries.ConfigFlowResult = dict
_ha_config_entries.OptionsFlow = _MockOptionsFlow

# data_entry_flow section mock


class _MockSection:
    """Mock section for data entry flows."""

    def __init__(self, schema, options=None):
        self.schema = schema
        self.options = options or {}

    def __call__(self, value):
        return self.schema(value)


_ha_data_entry_flow.section = _MockSection

# Entity registry
_ha_helpers_er.async_get = MagicMock()
_ha_helpers_er.EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"

# Area registry
_ha_helpers_ar.async_get = MagicMock()
_ha_helpers_ar.EVENT_AREA_REGISTRY_UPDATED = "area_registry_updated"

# Device registry
_ha_helpers_dr.async_get = MagicMock()
_ha_helpers_dr.EVENT_DEVICE_REGISTRY_UPDATED = "device_registry_updated"
_ha_helpers_dr.DeviceInfo = dict
_ha_helpers_dr.DeviceEntryType = MagicMock()
_ha_helpers_dr.DeviceEntryType.SERVICE = "service"

# Floor registry
_ha_helpers_fr.async_get = MagicMock()
_ha_helpers_fr.EVENT_FLOOR_REGISTRY_UPDATED = "floor_registry_updated"

# Exposed entities
_ha_components_ha_exposed.async_should_expose = MagicMock(return_value=True)

# STT platform mocks
_ha_components_stt = ModuleType("homeassistant.components.stt")
_ha_components_stt.AudioFormats = MagicMock()
_ha_components_stt.AudioFormats.WAV = "wav"
_ha_components_stt.AudioFormats.OGG = "ogg"
_ha_components_stt.AudioCodecs = MagicMock()
_ha_components_stt.AudioCodecs.PCM = "pcm"
_ha_components_stt.AudioCodecs.OPUS = "opus"
_ha_components_stt.AudioBitRates = MagicMock()
_ha_components_stt.AudioBitRates.BITRATE_16 = 16
_ha_components_stt.AudioSampleRates = MagicMock()
_ha_components_stt.AudioSampleRates.SAMPLERATE_16000 = 16000
_ha_components_stt.AudioChannels = MagicMock()
_ha_components_stt.AudioChannels.CHANNEL_MONO = 1
_ha_components_stt.SpeechMetadata = MagicMock
_ha_components_stt.SpeechResult = MagicMock
_ha_components_stt.SpeechResultState = MagicMock()
_ha_components_stt.SpeechResultState.SUCCESS = "success"
_ha_components_stt.SpeechResultState.ERROR = "error"
_ha_components_stt.SpeechToTextEntity = type(
    "SpeechToTextEntity",
    (),
    {"_attr_available": True, "async_write_ha_state": lambda self: None},
)

# Entity platform
_ha_helpers_ep = ModuleType("homeassistant.helpers.entity_platform")
_ha_helpers_ep.AddConfigEntryEntitiesCallback = MagicMock

# ── Sensor platform mocks (Chunk 4) ──
_ha_const = ModuleType("homeassistant.const")
_ha_components_sensor = ModuleType("homeassistant.components.sensor")


class _EntityCategory(StrEnum):
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


_ha_const.EntityCategory = _EntityCategory


class _SensorStateClass(StrEnum):
    MEASUREMENT = "measurement"
    TOTAL = "total"
    TOTAL_INCREASING = "total_increasing"


class _SensorDeviceClass(StrEnum):
    ENUM = "enum"


@dataclass(frozen=True, kw_only=True)
class _SensorEntityDescription:
    key: str = ""
    translation_key: str | None = None
    name: str | None = None
    icon: str | None = None
    native_unit_of_measurement: str | None = None
    suggested_display_precision: int | None = None
    state_class: _SensorStateClass | None = None
    entity_category: _EntityCategory | None = None
    entity_registry_enabled_default: bool = True
    device_class: _SensorDeviceClass | None = None
    options: list[str] | None = None


class _RestoreSensor:
    """Mock RestoreSensor base class."""

    _attr_native_value: Any = None
    _attr_should_poll: bool = True
    _attr_unique_id: str | None = None
    _attr_device_info: Any = None
    has_entity_name: bool = False
    entity_description: Any = None

    async def async_added_to_hass(self) -> None:
        pass

    async def async_will_remove_from_hass(self) -> None:
        pass

    async def async_get_last_sensor_data(self) -> Any:
        return None

    def async_write_ha_state(self) -> None:
        pass


_ha_components_sensor.RestoreSensor = _RestoreSensor
_ha_components_sensor.SensorEntityDescription = _SensorEntityDescription
_ha_components_sensor.SensorDeviceClass = _SensorDeviceClass
_ha_components_sensor.SensorStateClass = _SensorStateClass

# Selector helpers
_ha_helpers_selector = ModuleType("homeassistant.helpers.selector")
_ha_helpers_selector.TextSelector = MagicMock()
_ha_helpers_selector.TextSelectorConfig = MagicMock()
_ha_helpers_selector.SelectSelector = MagicMock()
_ha_helpers_selector.SelectSelectorConfig = MagicMock()
_ha_helpers_selector.SelectOptionDict = dict

# Register all mocked modules
for mod_name, mod in [
    ("homeassistant", _ha),
    ("homeassistant.core", _ha_core),
    ("homeassistant.config_entries", _ha_config_entries),
    ("homeassistant.data_entry_flow", _ha_data_entry_flow),
    ("homeassistant.helpers", _ha_helpers),
    ("homeassistant.helpers.config_validation", _ha_helpers_cv),
    ("homeassistant.helpers.entity_registry", _ha_helpers_er),
    ("homeassistant.helpers.area_registry", _ha_helpers_ar),
    ("homeassistant.helpers.device_registry", _ha_helpers_dr),
    ("homeassistant.helpers.floor_registry", _ha_helpers_fr),
    ("homeassistant.components", _ha_components),
    ("homeassistant.components.homeassistant", _ha_components_ha),
    (
        "homeassistant.components.homeassistant.exposed_entities",
        _ha_components_ha_exposed,
    ),
    ("homeassistant.components.stt", _ha_components_stt),
    ("homeassistant.helpers.entity_platform", _ha_helpers_ep),
    ("homeassistant.helpers.selector", _ha_helpers_selector),
    ("homeassistant.exceptions", _ha_exceptions),
    ("homeassistant.const", _ha_const),
    ("homeassistant.components.sensor", _ha_components_sensor),
]:
    sys.modules[mod_name] = mod

# Also mock voluptuous since config_flow uses it
try:
    import voluptuous  # noqa: F401
except ImportError:
    _vol = MagicMock()
    sys.modules["voluptuous"] = _vol

import pytest  # noqa: E402


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock(return_value=lambda: None)
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    hass.data = {}
    return hass

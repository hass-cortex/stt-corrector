"""Build phrase list from HA exposed entities and areas."""

from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    floor_registry as fr,
)

from .const import (
    AUTO_COLLECT_AREAS,
    AUTO_COLLECT_DEVICES,
    AUTO_COLLECT_ENTITIES,
    AUTO_COLLECT_FLOORS,
    DEFAULT_AUTO_COLLECT_SOURCES,
)

_LOGGER = logging.getLogger(__name__)

_RELEVANT_ACTIONS = {"create", "remove"}
_RELEVANT_FIELDS = {"name", "aliases", "disabled_by"}


class PhraseBuilder:
    """Build and cache phrase list from HA exposed entities and areas.

    Only includes entities exposed to the 'conversation' assistant,
    not all entities in the registry.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        custom_phrases: list[str],
        enabled_sources: list[str] | None = None,
    ) -> None:
        self._hass = hass
        self._custom_phrases = custom_phrases
        self._enabled_sources: set[str] = set(
            enabled_sources
            if enabled_sources is not None
            else DEFAULT_AUTO_COLLECT_SOURCES
        )
        self._cache: list[str] | None = None
        self._categories: dict[str, list[str]] = {}
        self._unsub_entity: Callable[[], None] | None = None
        self._unsub_area: Callable[[], None] | None = None
        self._unsub_device: Callable[[], None] | None = None
        self._unsub_floor: Callable[[], None] | None = None

    def update_custom_phrases(self, phrases: list[str]) -> None:
        """Update custom phrases and invalidate cache."""
        self._custom_phrases = phrases
        self._cache = None

    def update_sources(self, sources: list[str]) -> None:
        """Update enabled auto-collect sources and invalidate cache."""
        new_sources = set(sources)
        if new_sources != self._enabled_sources:
            self._enabled_sources = new_sources
            self._cache = None

    async def build(self) -> list[str]:
        """Return cached phrases, rebuild if invalidated.

        Collects from enabled sources:
        - Friendly names of entities exposed to voice assistants
        - Device names
        - Area names and aliases
        - Floor names and aliases
        - User-defined custom phrases (always included)
        """
        if self._cache is not None:
            return self._cache

        entity_names: set[str] = set()
        device_names: set[str] = set()
        area_names: set[str] = set()
        floor_names: set[str] = set()

        if AUTO_COLLECT_ENTITIES in self._enabled_sources:
            ent_reg = er.async_get(self._hass)
            for entry in ent_reg.entities.values():
                if entry.disabled_by is not None:
                    continue
                if not async_should_expose(self._hass, "conversation", entry.entity_id):
                    continue
                state = self._hass.states.get(entry.entity_id)
                if state and (name := state.attributes.get("friendly_name")):
                    entity_names.add(name)
                if entry.aliases:
                    entity_names.update(entry.aliases)

        if AUTO_COLLECT_DEVICES in self._enabled_sources:
            dev_reg = dr.async_get(self._hass)
            for device in dev_reg.devices.values():
                if device.disabled_by is not None:
                    continue
                name = device.name_by_user or device.name
                if name:
                    device_names.add(name)

        if AUTO_COLLECT_AREAS in self._enabled_sources:
            area_reg = ar.async_get(self._hass)
            for area in area_reg.async_list_areas():
                area_names.add(area.name)
                if area.aliases:
                    area_names.update(area.aliases)

        if AUTO_COLLECT_FLOORS in self._enabled_sources:
            floor_reg = fr.async_get(self._hass)
            for floor in floor_reg.async_list_floors():
                floor_names.add(floor.name)
                if floor.aliases:
                    floor_names.update(floor.aliases)

        # Merge enabled sources + custom phrases (always included)
        phrases = entity_names | device_names | area_names | floor_names
        phrases.update(self._custom_phrases)

        self._cache = list(phrases)
        self._categories = {
            "entities": sorted(entity_names),
            "devices": sorted(device_names),
            "areas": sorted(area_names),
            "floors": sorted(floor_names),
            "custom": list(self._custom_phrases),
        }
        return self._cache

    @callback
    def async_start_listening(self) -> None:
        """Subscribe to entity, area, device, and floor registry change events."""
        self._unsub_entity = self._hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._handle_registry_event
        )
        self._unsub_area = self._hass.bus.async_listen(
            ar.EVENT_AREA_REGISTRY_UPDATED, self._handle_registry_event
        )
        self._unsub_device = self._hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, self._handle_registry_event
        )
        self._unsub_floor = self._hass.bus.async_listen(
            fr.EVENT_FLOOR_REGISTRY_UPDATED, self._handle_registry_event
        )

    @callback
    def async_stop_listening(self) -> None:
        """Unsubscribe from registry events."""
        for unsub_attr in (
            "_unsub_entity",
            "_unsub_area",
            "_unsub_device",
            "_unsub_floor",
        ):
            unsub = getattr(self, unsub_attr)
            if unsub is not None:
                unsub()
                setattr(self, unsub_attr, None)

    @callback
    def _handle_registry_event(self, event: Event) -> None:
        """Invalidate cache on relevant registry changes.

        Invalidates on:
        - Entity/area created or removed
        - Entity/area name, aliases, or disabled_by changed
        """
        data = event.data
        action = data.get("action", "")
        if action in _RELEVANT_ACTIONS:
            self._cache = None
            return
        if action == "update":
            changes = data.get("changes", {})
            if changes and _RELEVANT_FIELDS & set(changes.keys()):
                self._cache = None

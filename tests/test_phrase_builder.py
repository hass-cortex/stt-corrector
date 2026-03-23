"""Tests for PhraseBuilder."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.stt_corrector.phrase_builder import PhraseBuilder


def _make_entity_entry(
    entity_id: str,
    friendly_name: str | None = None,
    aliases: set[str] | None = None,
    disabled_by: str | None = None,
) -> SimpleNamespace:
    """Create a mock entity registry entry."""
    return SimpleNamespace(
        entity_id=entity_id,
        aliases=aliases,
        disabled_by=disabled_by,
        _friendly_name=friendly_name,
    )


def _make_area(
    name: str,
    aliases: set[str] | None = None,
) -> SimpleNamespace:
    """Create a mock area registry entry."""
    return SimpleNamespace(name=name, aliases=aliases)


def _make_device(
    name: str | None = None,
    name_by_user: str | None = None,
    disabled_by: str | None = None,
) -> SimpleNamespace:
    """Create a mock device registry entry."""
    return SimpleNamespace(
        name=name, name_by_user=name_by_user, disabled_by=disabled_by
    )


def _make_floor(
    name: str,
    aliases: set[str] | None = None,
) -> SimpleNamespace:
    """Create a mock floor registry entry."""
    return SimpleNamespace(name=name, aliases=aliases)


def _setup_registries(
    mock_hass: MagicMock,
    entities: list[SimpleNamespace] | None = None,
    areas: list[SimpleNamespace] | None = None,
    devices: list[SimpleNamespace] | None = None,
    floors: list[SimpleNamespace] | None = None,
) -> None:
    """Set up mock entity, area, device, and floor registries on mock_hass."""
    import homeassistant.helpers.area_registry as ar
    import homeassistant.helpers.device_registry as dr
    import homeassistant.helpers.entity_registry as er
    import homeassistant.helpers.floor_registry as fr

    entities = entities or []
    areas = areas or []
    devices = devices or []
    floors = floors or []

    # Entity registry
    ent_reg = MagicMock()
    ent_reg.entities = MagicMock()
    ent_reg.entities.values.return_value = entities
    er.async_get.return_value = ent_reg

    # Area registry
    area_reg = MagicMock()
    area_reg.async_list_areas.return_value = areas
    ar.async_get.return_value = area_reg

    # Device registry
    dev_reg = MagicMock()
    dev_reg.devices = MagicMock()
    dev_reg.devices.values.return_value = devices
    dr.async_get.return_value = dev_reg

    # Floor registry
    floor_reg = MagicMock()
    floor_reg.async_list_floors.return_value = floors
    fr.async_get.return_value = floor_reg

    # Set up states.get to return friendly names
    def _get_state(entity_id: str):
        for ent in entities:
            if ent.entity_id == entity_id and ent._friendly_name:
                state = MagicMock()
                state.attributes = {"friendly_name": ent._friendly_name}
                return state
        return None

    mock_hass.states.get.side_effect = _get_state


@pytest.mark.asyncio
async def test_build_collects_entity_friendly_names(mock_hass):
    """Entity friendly names should be collected."""
    _setup_registries(
        mock_hass,
        entities=[
            _make_entity_entry("light.living_room", friendly_name="Living Room Light"),
            _make_entity_entry("switch.kitchen", friendly_name="Kitchen Switch"),
        ],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    phrases = await builder.build()
    assert "Living Room Light" in phrases
    assert "Kitchen Switch" in phrases


@pytest.mark.asyncio
async def test_build_skips_disabled_entities(mock_hass):
    """Disabled entities should be skipped."""
    _setup_registries(
        mock_hass,
        entities=[
            _make_entity_entry("light.ok", friendly_name="OK Light"),
            _make_entity_entry(
                "light.disabled",
                friendly_name="Disabled Light",
                disabled_by="user",
            ),
        ],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    phrases = await builder.build()
    assert "OK Light" in phrases
    assert "Disabled Light" not in phrases


@pytest.mark.asyncio
async def test_build_collects_entity_aliases(mock_hass):
    """Entity aliases should be collected."""
    _setup_registries(
        mock_hass,
        entities=[
            _make_entity_entry(
                "light.lr",
                friendly_name="Living Room",
                aliases={"LR Light", "Main Light"},
            ),
        ],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    phrases = await builder.build()
    assert "Living Room" in phrases
    assert "LR Light" in phrases
    assert "Main Light" in phrases


@pytest.mark.asyncio
async def test_build_collects_area_names_and_aliases(mock_hass):
    """Area names and aliases should be collected."""
    _setup_registries(
        mock_hass,
        areas=[
            _make_area("Kitchen", aliases={"Cooking Area"}),
            _make_area("Living Room"),
        ],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    phrases = await builder.build()
    assert "Kitchen" in phrases
    assert "Cooking Area" in phrases
    assert "Living Room" in phrases


@pytest.mark.asyncio
async def test_build_includes_custom_phrases(mock_hass):
    """User-defined custom phrases should be included."""
    _setup_registries(mock_hass)
    builder = PhraseBuilder(mock_hass, custom_phrases=["Hey Jarvis", "Goodnight"])
    phrases = await builder.build()
    assert "Hey Jarvis" in phrases
    assert "Goodnight" in phrases


@pytest.mark.asyncio
async def test_build_caches_result(mock_hass):
    """Second build() call should return cached result without re-querying."""
    import homeassistant.helpers.entity_registry as er

    _setup_registries(
        mock_hass,
        entities=[_make_entity_entry("light.a", friendly_name="Light A")],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])

    call_count_before = er.async_get.call_count
    first = await builder.build()
    second = await builder.build()

    assert first is second
    # async_get should only be called once (for the first build), not for the cached second
    assert er.async_get.call_count == call_count_before + 1


@pytest.mark.asyncio
async def test_cache_invalidated_on_create(mock_hass):
    """Cache should be invalidated when an entity is created."""
    import homeassistant.helpers.entity_registry as er

    _setup_registries(
        mock_hass,
        entities=[_make_entity_entry("light.a", friendly_name="Light A")],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])

    await builder.build()
    initial_call_count = er.async_get.call_count

    # Simulate a "create" event
    event = MagicMock()
    event.data = {"action": "create"}
    builder._handle_registry_event(event)

    # Cache should be invalidated
    await builder.build()
    assert er.async_get.call_count == initial_call_count + 1


@pytest.mark.asyncio
async def test_cache_invalidated_on_remove(mock_hass):
    """Cache should be invalidated when an entity is removed."""
    import homeassistant.helpers.entity_registry as er

    _setup_registries(
        mock_hass,
        entities=[_make_entity_entry("light.a", friendly_name="Light A")],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])

    await builder.build()
    initial_call_count = er.async_get.call_count

    event = MagicMock()
    event.data = {"action": "remove"}
    builder._handle_registry_event(event)

    await builder.build()
    assert er.async_get.call_count == initial_call_count + 1


@pytest.mark.asyncio
async def test_cache_not_invalidated_on_irrelevant_update(mock_hass):
    """Cache should NOT be invalidated on irrelevant field changes."""
    import homeassistant.helpers.entity_registry as er

    _setup_registries(
        mock_hass,
        entities=[_make_entity_entry("light.a", friendly_name="Light A")],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])

    await builder.build()
    initial_call_count = er.async_get.call_count

    # An update to an irrelevant field should not invalidate
    event = MagicMock()
    event.data = {"action": "update", "changes": {"icon": "mdi:lightbulb"}}
    builder._handle_registry_event(event)

    await builder.build()
    # Still cached — no extra async_get call
    assert er.async_get.call_count == initial_call_count


@pytest.mark.asyncio
async def test_cache_invalidated_on_name_change(mock_hass):
    """Cache should be invalidated on entity name change."""
    import homeassistant.helpers.entity_registry as er

    _setup_registries(
        mock_hass,
        entities=[_make_entity_entry("light.a", friendly_name="Light A")],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])

    await builder.build()
    initial_call_count = er.async_get.call_count

    event = MagicMock()
    event.data = {"action": "update", "changes": {"name": "New Name"}}
    builder._handle_registry_event(event)

    await builder.build()
    assert er.async_get.call_count == initial_call_count + 1


@pytest.mark.asyncio
async def test_cache_invalidated_on_aliases_change(mock_hass):
    """Cache should be invalidated on aliases change."""
    import homeassistant.helpers.entity_registry as er

    _setup_registries(
        mock_hass,
        entities=[_make_entity_entry("light.a", friendly_name="Light A")],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])

    await builder.build()
    initial_call_count = er.async_get.call_count

    event = MagicMock()
    event.data = {"action": "update", "changes": {"aliases": {"New Alias"}}}
    builder._handle_registry_event(event)

    await builder.build()
    assert er.async_get.call_count == initial_call_count + 1


@pytest.mark.asyncio
async def test_cache_invalidated_on_disabled_by_change(mock_hass):
    """Cache should be invalidated when disabled_by changes."""
    import homeassistant.helpers.entity_registry as er

    _setup_registries(
        mock_hass,
        entities=[_make_entity_entry("light.a", friendly_name="Light A")],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])

    await builder.build()
    initial_call_count = er.async_get.call_count

    event = MagicMock()
    event.data = {"action": "update", "changes": {"disabled_by": "user"}}
    builder._handle_registry_event(event)

    await builder.build()
    assert er.async_get.call_count == initial_call_count + 1


def test_async_start_listening_subscribes(mock_hass):
    """async_start_listening should subscribe to all registry events."""
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    builder.async_start_listening()

    calls = mock_hass.bus.async_listen.call_args_list
    event_types = [call.args[0] for call in calls]
    assert "entity_registry_updated" in event_types
    assert "area_registry_updated" in event_types
    assert "device_registry_updated" in event_types
    assert "floor_registry_updated" in event_types


def test_async_stop_listening_unsubscribes(mock_hass):
    """async_stop_listening should call unsubscribe callbacks."""
    unsub_entity = MagicMock()
    unsub_area = MagicMock()
    unsub_device = MagicMock()
    unsub_floor = MagicMock()
    mock_hass.bus.async_listen.side_effect = [
        unsub_entity,
        unsub_area,
        unsub_device,
        unsub_floor,
    ]

    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    builder.async_start_listening()
    builder.async_stop_listening()

    unsub_entity.assert_called_once()
    unsub_area.assert_called_once()
    unsub_device.assert_called_once()
    unsub_floor.assert_called_once()


def test_async_stop_listening_idempotent(mock_hass):
    """Calling async_stop_listening without start should not raise."""
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    # Should not raise
    builder.async_stop_listening()


@pytest.mark.asyncio
async def test_build_deduplicates(mock_hass):
    """Duplicate phrases from entities, areas, and custom should be deduplicated."""
    _setup_registries(
        mock_hass,
        entities=[
            _make_entity_entry(
                "light.lr",
                friendly_name="Living Room",
                aliases={"Living Room"},
            ),
        ],
        areas=[_make_area("Living Room")],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=["Living Room"])
    phrases = await builder.build()
    assert phrases.count("Living Room") == 1


@pytest.mark.asyncio
async def test_build_no_event_with_empty_changes(mock_hass):
    """Update event with empty changes dict should NOT invalidate cache."""
    import homeassistant.helpers.entity_registry as er

    _setup_registries(mock_hass)
    builder = PhraseBuilder(mock_hass, custom_phrases=[])

    await builder.build()
    initial_call_count = er.async_get.call_count

    event = MagicMock()
    event.data = {"action": "update", "changes": {}}
    builder._handle_registry_event(event)

    await builder.build()
    assert er.async_get.call_count == initial_call_count


@pytest.mark.asyncio
async def test_update_custom_phrases_invalidates_cache(mock_hass):
    """update_custom_phrases should invalidate the cache."""
    _setup_registries(mock_hass)
    builder = PhraseBuilder(mock_hass, custom_phrases=["old"])
    phrases1 = await builder.build()
    assert "old" in phrases1

    builder.update_custom_phrases(["new"])
    phrases2 = await builder.build()
    assert "new" in phrases2
    assert "old" not in phrases2


@pytest.mark.asyncio
async def test_update_sources_invalidates_cache(mock_hass):
    """update_sources should invalidate cache when sources change."""
    _setup_registries(mock_hass)
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    await builder.build()

    # Same sources — should NOT invalidate
    builder.update_sources(["floors", "areas", "devices", "entities"])
    assert builder._cache is not None

    # Different sources — should invalidate
    builder.update_sources(["areas"])
    assert builder._cache is None


@pytest.mark.asyncio
async def test_build_collects_device_names(mock_hass):
    """Device names should be collected (name_by_user preferred over name)."""
    _setup_registries(
        mock_hass,
        devices=[
            _make_device(name="Kitchen Speaker"),
            _make_device(name="Living Room TV", name_by_user="TV"),
        ],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    phrases = await builder.build()
    assert "Kitchen Speaker" in phrases
    assert "TV" in phrases
    assert "Living Room TV" not in phrases  # name_by_user takes precedence


@pytest.mark.asyncio
async def test_build_skips_disabled_devices(mock_hass):
    """Disabled devices should be skipped."""
    _setup_registries(
        mock_hass,
        devices=[
            _make_device(name="OK Device"),
            _make_device(name="Disabled Device", disabled_by="user"),
        ],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    phrases = await builder.build()
    assert "OK Device" in phrases
    assert "Disabled Device" not in phrases


@pytest.mark.asyncio
async def test_build_collects_floor_names_and_aliases(mock_hass):
    """Floor names and aliases should be collected."""
    _setup_registries(
        mock_hass,
        floors=[
            _make_floor("Ground Floor", aliases={"1F", "First Floor"}),
            _make_floor("Basement"),
        ],
    )
    builder = PhraseBuilder(mock_hass, custom_phrases=[])
    phrases = await builder.build()
    assert "Ground Floor" in phrases
    assert "1F" in phrases
    assert "First Floor" in phrases
    assert "Basement" in phrases

"""Tests for stt_corrector __init__.py (setup/unload/options update)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.stt_corrector.models import STTCorrectorRuntimeData


def _make_config_entry(
    data: dict | None = None,
    options: dict | None = None,
    entry_id: str = "test_entry_123",
) -> MagicMock:
    """Create a mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = data or {"wrapped_entity_id": "stt.azure_stt"}
    entry.options = options or {}
    entry.runtime_data = STTCorrectorRuntimeData()

    _listeners: list = []

    def _add_update_listener(listener):
        _listeners.append(listener)
        return lambda: _listeners.remove(listener)

    entry.add_update_listener = MagicMock(side_effect=_add_update_listener)
    entry._listeners = _listeners
    entry.async_on_unload = MagicMock(side_effect=lambda unsub: unsub)

    return entry


class TestAsyncSetup:
    """Test async_setup (service registration)."""

    @pytest.mark.asyncio
    async def test_async_setup_registers_services(self, mock_hass):
        """async_setup should register all services."""
        from custom_components.stt_corrector import async_setup

        result = await async_setup(mock_hass, {})

        assert result is True
        assert mock_hass.services.async_register.call_count == 9


class TestAsyncSetupEntry:
    """Test async_setup_entry."""

    @pytest.mark.asyncio
    async def test_async_setup_entry_success(self, mock_hass):
        """Successful setup should forward entry setup."""
        entry = _make_config_entry()

        mock_hass.config_entries.async_forward_entry_setups = AsyncMock()
        mock_hass.async_add_executor_job = AsyncMock()

        from custom_components.stt_corrector import async_setup_entry

        result = await async_setup_entry(mock_hass, entry)

        assert result is True
        mock_hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
            entry, ["stt", "sensor"]
        )

    @pytest.mark.asyncio
    async def test_async_setup_entry_sets_runtime_data(self, mock_hass):
        """Setup should set runtime_data on the entry."""
        entry = _make_config_entry()
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock()
        mock_hass.async_add_executor_job = AsyncMock()

        from custom_components.stt_corrector import async_setup_entry

        await async_setup_entry(mock_hass, entry)

        assert isinstance(entry.runtime_data, STTCorrectorRuntimeData)

    @pytest.mark.asyncio
    async def test_async_setup_entry_registers_update_listener(self, mock_hass):
        """Setup should register an options update listener."""
        entry = _make_config_entry()
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock()
        mock_hass.async_add_executor_job = AsyncMock()

        from custom_components.stt_corrector import async_setup_entry

        await async_setup_entry(mock_hass, entry)

        entry.add_update_listener.assert_called_once()


class TestAsyncUnloadEntry:
    """Test async_unload_entry."""

    @pytest.mark.asyncio
    async def test_async_unload_entry_success(self, mock_hass):
        """Unload should call async_unload_platforms."""
        entry = _make_config_entry()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        from custom_components.stt_corrector import async_unload_entry

        result = await async_unload_entry(mock_hass, entry)

        assert result is True
        mock_hass.config_entries.async_unload_platforms.assert_awaited_once_with(
            entry, ["stt", "sensor"]
        )

    @pytest.mark.asyncio
    async def test_async_unload_entry_failure(self, mock_hass):
        """Unload returning False should propagate."""
        entry = _make_config_entry()
        mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)

        from custom_components.stt_corrector import async_unload_entry

        result = await async_unload_entry(mock_hass, entry)

        assert result is False


class TestUpdateOptions:
    """Test _async_update_options listener."""

    @pytest.mark.asyncio
    async def test_update_options_rebuilds(self, mock_hass):
        """Options update should call rebuild_from_options on the entity."""
        entry = _make_config_entry()

        mock_entity = MagicMock()
        mock_entity.rebuild_from_options = MagicMock()
        entry.runtime_data = STTCorrectorRuntimeData(entity=mock_entity)

        from custom_components.stt_corrector import _async_update_options

        await _async_update_options(mock_hass, entry)

        mock_entity.rebuild_from_options.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_options_no_entity(self, mock_hass):
        """Options update with no entity should not raise."""
        entry = _make_config_entry()
        entry.runtime_data = STTCorrectorRuntimeData()

        from custom_components.stt_corrector import _async_update_options

        # Should not raise
        await _async_update_options(mock_hass, entry)

"""Tests for STT Corrector diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.stt_corrector.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.stt_corrector.models import STTCorrectorRuntimeData


def _make_entry(data: dict | None = None, options: dict | None = None) -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = data or {"wrapped_entity_id": "stt.azure_stt"}
    entry.options = options or {"enable_fuzzy_matching": True}
    entry.runtime_data = STTCorrectorRuntimeData()
    return entry


class TestDiagnostics:
    """Test diagnostics output."""

    @pytest.mark.asyncio
    async def test_includes_data_and_options(self):
        """Diagnostics should include config data and options."""
        hass = MagicMock()
        entry = _make_entry()

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["config_entry"]["data"]["wrapped_entity_id"] == "stt.azure_stt"
        assert result["config_entry"]["options"]["enable_fuzzy_matching"] is True

    @pytest.mark.asyncio
    async def test_structure(self):
        """Diagnostics should have expected structure."""
        hass = MagicMock()
        entry = _make_entry()

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert "config_entry" in result
        assert "data" in result["config_entry"]
        assert "options" in result["config_entry"]

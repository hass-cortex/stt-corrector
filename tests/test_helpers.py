"""Tests for helpers module."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.stt_corrector.helpers import find_corrected_stt_entity
from custom_components.stt_corrector.models import STTCorrectorRuntimeData


class TestFindCorrectedSTTEntity:
    def test_returns_entity_from_entry(self):
        entity = MagicMock()
        entry = MagicMock()
        entry.runtime_data = STTCorrectorRuntimeData(entity=entity)
        hass = MagicMock()

        result = find_corrected_stt_entity(hass, entry)
        assert result is entity

    def test_returns_none_when_no_runtime_data(self):
        entry = MagicMock(spec=[])  # no runtime_data attribute
        hass = MagicMock()

        result = find_corrected_stt_entity(hass, entry)
        assert result is None

    def test_returns_none_when_entity_is_none(self):
        entry = MagicMock()
        entry.runtime_data = STTCorrectorRuntimeData(entity=None)
        hass = MagicMock()

        result = find_corrected_stt_entity(hass, entry)
        assert result is None

    def test_searches_all_entries_when_no_entry_given(self):
        entity = MagicMock()
        entry1 = MagicMock()
        entry1.runtime_data = STTCorrectorRuntimeData(entity=entity)
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = [entry1]

        result = find_corrected_stt_entity(hass)
        assert result is entity
        hass.config_entries.async_entries.assert_called_once_with("stt_corrector")

    def test_returns_none_when_no_entries(self):
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []

        result = find_corrected_stt_entity(hass)
        assert result is None

    def test_skips_entries_without_runtime_data(self):
        entry1 = MagicMock(spec=[])  # no runtime_data
        entity2 = MagicMock()
        entry2 = MagicMock()
        entry2.runtime_data = STTCorrectorRuntimeData(entity=entity2)
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = [entry1, entry2]

        result = find_corrected_stt_entity(hass)
        assert result is entity2

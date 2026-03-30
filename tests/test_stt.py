"""Tests for CorrectedSTTEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.stt_corrector.stt import CorrectedSTTEntity


def _make_config_entry(entry_id="test_entry", options=None):
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.title = "Corrected STT"
    entry.data = {"wrapped_entity_id": "mock_registry_id"}
    entry.options = options or {}
    entry.runtime_data = MagicMock()
    entry.runtime_data.sensors = []
    return entry


def _make_wrapped_entity(
    text="hello world",
    result_state="success",
    supported_languages=None,
):
    """Create a mock wrapped STT entity."""
    wrapped = MagicMock()
    wrapped.supported_languages = supported_languages or ["en-US", "zh-TW"]
    wrapped.supported_formats = ["wav"]
    wrapped.supported_codecs = ["pcm"]
    wrapped.supported_bit_rates = [16]
    wrapped.supported_sample_rates = [16000]
    wrapped.supported_channels = [1]

    result = MagicMock()
    result.result = result_state
    result.text = text
    wrapped.async_process_audio_stream = AsyncMock(return_value=result)
    return wrapped


async def _audio_stream(chunks=None):
    """Create a test audio stream."""
    for chunk in chunks or [b"audio_data"]:
        yield chunk


class TestCorrectedSTTEntityProxy:
    @pytest.mark.asyncio
    async def test_forwards_audio_to_wrapped_entity(self, mock_hass):
        entry = _make_config_entry()
        wrapped = _make_wrapped_entity(text="hello")
        entity = CorrectedSTTEntity(mock_hass, entry)

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            metadata = MagicMock(language="en-US")
            result = await entity.async_process_audio_stream(metadata, _audio_stream())

        wrapped.async_process_audio_stream.assert_called_once()
        assert result.text is not None

    @pytest.mark.asyncio
    async def test_returns_error_when_wrapped_unavailable(self, mock_hass):
        entry = _make_config_entry()
        entity = CorrectedSTTEntity(mock_hass, entry)

        with patch.object(entity, "_get_wrapped_entity", return_value=None):
            metadata = MagicMock(language="en-US")
            result = await entity.async_process_audio_stream(metadata, _audio_stream())

        assert result.result == "error"

    @pytest.mark.asyncio
    async def test_applies_correction_on_success(self, mock_hass):
        entry = _make_config_entry()
        wrapped = _make_wrapped_entity(text="hello")
        entity = CorrectedSTTEntity(mock_hass, entry)

        mock_correction = MagicMock()
        mock_correction.corrected = "hello corrected"
        mock_correction.original = "hello"
        mock_correction.changes = []
        mock_correction.candidates = []
        mock_corrector = MagicMock()
        mock_corrector.diagnose.return_value = mock_correction
        entity._corrector = mock_corrector

        with patch.object(entity, "_build_corrector", return_value=mock_corrector):
            with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
                with patch.object(entity, "_phrase_builder") as mock_pb:
                    mock_pb.build = AsyncMock(return_value=["phrase1"])
                    metadata = MagicMock(language="en-US")
                    result = await entity.async_process_audio_stream(
                        metadata, _audio_stream()
                    )

        assert result.text == "hello corrected"

    @pytest.mark.asyncio
    async def test_passes_through_error_from_wrapped(self, mock_hass):
        entry = _make_config_entry()
        wrapped = _make_wrapped_entity(text=None, result_state="error")
        entity = CorrectedSTTEntity(mock_hass, entry)

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            metadata = MagicMock(language="en-US")
            result = await entity.async_process_audio_stream(metadata, _audio_stream())

        assert result.result == "error"

    @pytest.mark.asyncio
    async def test_buffers_and_replays_audio(self, mock_hass):
        entry = _make_config_entry()
        wrapped = _make_wrapped_entity(text="ok")
        entity = CorrectedSTTEntity(mock_hass, entry)

        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        captured_chunks = []

        async def capture_stream(metadata, stream):
            async for chunk in stream:
                captured_chunks.append(chunk)
            result = MagicMock()
            result.result = "success"
            result.text = "ok"
            return result

        wrapped.async_process_audio_stream = capture_stream

        entity._corrector = MagicMock()
        entity._corrector.diagnose.return_value = MagicMock(
            corrected="ok", original="ok", changes=[], candidates=[]
        )

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            with patch.object(entity, "_phrase_builder") as mock_pb:
                mock_pb.build = AsyncMock(return_value=[])
                metadata = MagicMock(language="en-US")
                await entity.async_process_audio_stream(metadata, _audio_stream(chunks))

        assert captured_chunks == chunks

    @pytest.mark.asyncio
    async def test_pushes_stats_to_sensors(self, mock_hass):
        entry = _make_config_entry()
        wrapped = _make_wrapped_entity(text="hello")
        sensor = MagicMock()
        entry.runtime_data.sensors = [sensor]
        entity = CorrectedSTTEntity(mock_hass, entry)

        entity._corrector = MagicMock()
        entity._corrector.diagnose.return_value = MagicMock(
            corrected="hello", original="hello", changes=[], candidates=[]
        )

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            with patch.object(entity, "_phrase_builder") as mock_pb:
                mock_pb.build = AsyncMock(return_value=[])
                metadata = MagicMock(language="en-US")
                await entity.async_process_audio_stream(metadata, _audio_stream())

        sensor.handle_transcription.assert_called_once()
        stats = sensor.handle_transcription.call_args[0][0]
        assert stats.result_state == "success"


class TestCorrectedSTTEntityProperties:
    def test_proxies_supported_languages(self, mock_hass):
        entry = _make_config_entry()
        entity = CorrectedSTTEntity(mock_hass, entry)
        wrapped = _make_wrapped_entity(supported_languages=["en-US", "zh-TW"])

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            langs = entity.supported_languages
        assert langs == ["en-US", "zh-TW"]

    def test_returns_empty_when_wrapped_unavailable(self, mock_hass):
        entry = _make_config_entry()
        entity = CorrectedSTTEntity(mock_hass, entry)

        with patch.object(entity, "_get_wrapped_entity", return_value=None):
            langs = entity.supported_languages
        assert langs == []


class TestCorrectedSTTEntityLifecycle:
    @pytest.mark.asyncio
    async def test_registers_in_runtime_data(self, mock_hass):
        entry = _make_config_entry()
        entity = CorrectedSTTEntity(mock_hass, entry)
        await entity.async_added_to_hass()
        assert entry.runtime_data.entity is entity

    @pytest.mark.asyncio
    async def test_starts_phrase_builder_listening(self, mock_hass):
        entry = _make_config_entry()
        entity = CorrectedSTTEntity(mock_hass, entry)
        entity._phrase_builder = MagicMock()
        await entity.async_added_to_hass()
        entity._phrase_builder.async_start_listening.assert_called_once()

    @pytest.mark.asyncio
    async def test_stops_phrase_builder_on_remove(self, mock_hass):
        entry = _make_config_entry()
        entity = CorrectedSTTEntity(mock_hass, entry)
        entity._phrase_builder = MagicMock()
        await entity.async_will_remove_from_hass()
        entity._phrase_builder.async_stop_listening.assert_called_once()

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

        with (
            patch.object(entity, "_build_corrector", return_value=mock_corrector),
            patch.object(entity, "_get_wrapped_entity", return_value=wrapped),
            patch.object(entity, "_phrase_builder") as mock_pb,
        ):
            mock_pb.build = AsyncMock(return_value=["phrase1"])
            metadata = MagicMock(language="en-US")
            result = await entity.async_process_audio_stream(metadata, _audio_stream())

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

        with (
            patch.object(entity, "_get_wrapped_entity", return_value=wrapped),
            patch.object(entity, "_phrase_builder") as mock_pb,
        ):
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

        with (
            patch.object(entity, "_get_wrapped_entity", return_value=wrapped),
            patch.object(entity, "_phrase_builder") as mock_pb,
        ):
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


class TestSupportedLanguagesMerge:
    """Test supported_languages includes mapped locales from language config."""

    def test_adds_mapped_locale_not_in_native_list(self, mock_hass):
        entry = _make_config_entry(
            options={
                "language_config": {
                    "mandarin": {
                        "zh-tw": {"stt_language": "zh"},
                    }
                }
            }
        )
        entity = CorrectedSTTEntity(mock_hass, entry)
        wrapped = _make_wrapped_entity(supported_languages=["zh", "en-US"])

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            langs = entity.supported_languages

        assert "zh-TW" in langs
        assert "zh" in langs
        assert "en-US" in langs

    def test_no_duplicate_when_native_supports_locale(self, mock_hass):
        entry = _make_config_entry(
            options={
                "language_config": {
                    "mandarin": {
                        "zh-tw": {"stt_language": "zh-TW"},
                    }
                }
            }
        )
        entity = CorrectedSTTEntity(mock_hass, entry)
        wrapped = _make_wrapped_entity(supported_languages=["zh-TW", "en-US"])

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            langs = entity.supported_languages

        assert langs.count("zh-TW") == 1

    def test_empty_stt_language_not_added(self, mock_hass):
        entry = _make_config_entry(
            options={
                "language_config": {
                    "mandarin": {
                        "zh-cn": {"stt_language": ""},
                    }
                }
            }
        )
        entity = CorrectedSTTEntity(mock_hass, entry)
        wrapped = _make_wrapped_entity(supported_languages=["zh"])

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            langs = entity.supported_languages

        assert "zh-CN" not in langs
        assert "zh-cn" not in langs

    def test_no_language_config_auto_computes_defaults(self, mock_hass):
        """Without stored config, auto-compute defaults via prefix matching."""
        entry = _make_config_entry(options={})
        entity = CorrectedSTTEntity(mock_hass, entry)
        wrapped = _make_wrapped_entity(supported_languages=["en-US", "zh"])

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            langs = entity.supported_languages

        # zh prefix-matches zh-TW, zh-HK, zh-CN from MandarinModule
        assert "en-US" in langs
        assert "zh" in langs
        assert "zh-TW" in langs
        assert "zh-HK" in langs
        assert "zh-CN" in langs

    def test_no_prefix_match_no_auto_add(self, mock_hass):
        """When underlying STT has no matching language, locales are not added."""
        entry = _make_config_entry(options={})
        entity = CorrectedSTTEntity(mock_hass, entry)
        wrapped = _make_wrapped_entity(supported_languages=["en-US", "ja-JP"])

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            langs = entity.supported_languages

        assert langs == ["en-US", "ja-JP"]
        assert "zh-TW" not in langs

    def test_multiple_locales_mapped(self, mock_hass):
        entry = _make_config_entry(
            options={
                "language_config": {
                    "mandarin": {
                        "zh-tw": {"stt_language": "zh"},
                        "zh-hk": {"stt_language": "zh"},
                        "zh-cn": {"stt_language": ""},
                    }
                }
            }
        )
        entity = CorrectedSTTEntity(mock_hass, entry)
        wrapped = _make_wrapped_entity(supported_languages=["zh"])

        with patch.object(entity, "_get_wrapped_entity", return_value=wrapped):
            langs = entity.supported_languages

        assert "zh" in langs
        assert "zh-TW" in langs
        assert "zh-HK" in langs
        assert "zh-CN" not in langs

    def test_wrapped_unavailable_returns_empty(self, mock_hass):
        entry = _make_config_entry(
            options={
                "language_config": {
                    "mandarin": {
                        "zh-tw": {"stt_language": "zh"},
                    }
                }
            }
        )
        entity = CorrectedSTTEntity(mock_hass, entry)

        with patch.object(entity, "_get_wrapped_entity", return_value=None):
            langs = entity.supported_languages

        assert langs == []


class TestLanguageRemapping:
    """Test language remapping in async_process_audio_stream."""

    @pytest.mark.asyncio
    async def test_remaps_language_to_underlying_stt(self, mock_hass):
        """When locale has stt_language mapping, forward mapped language to wrapped entity."""
        entry = _make_config_entry(
            options={
                "language_config": {
                    "mandarin": {
                        "zh-tw": {"stt_language": "zh", "script_conversion": "s2tw"},
                    }
                }
            }
        )
        wrapped = _make_wrapped_entity(text="你好", supported_languages=["zh"])
        entity = CorrectedSTTEntity(mock_hass, entry)

        entity._corrector = MagicMock()
        entity._corrector.diagnose.return_value = MagicMock(
            corrected="你好", original="你好", changes=[], candidates=[]
        )

        with (
            patch.object(entity, "_get_wrapped_entity", return_value=wrapped),
            patch.object(entity, "_phrase_builder") as mock_pb,
        ):
            mock_pb.build = AsyncMock(return_value=[])
            metadata = MagicMock(language="zh-TW")
            metadata.format = "wav"
            metadata.codec = "pcm"
            metadata.bit_rate = 16
            metadata.sample_rate = 16000
            metadata.channel = 1
            await entity.async_process_audio_stream(metadata, _audio_stream())

        # Verify the wrapped entity received "zh" not "zh-TW"
        call_args = wrapped.async_process_audio_stream.call_args
        forwarded_metadata = call_args[0][0]
        assert forwarded_metadata.language == "zh"

    @pytest.mark.asyncio
    async def test_no_remap_when_no_mapping(self, mock_hass):
        """When locale has no stt_language mapping, forward original language."""
        entry = _make_config_entry(options={})
        wrapped = _make_wrapped_entity(text="hello", supported_languages=["en-US"])
        entity = CorrectedSTTEntity(mock_hass, entry)

        entity._corrector = MagicMock()
        entity._corrector.diagnose.return_value = MagicMock(
            corrected="hello", original="hello", changes=[], candidates=[]
        )

        with (
            patch.object(entity, "_get_wrapped_entity", return_value=wrapped),
            patch.object(entity, "_phrase_builder") as mock_pb,
        ):
            mock_pb.build = AsyncMock(return_value=[])
            metadata = MagicMock(language="en-US")
            await entity.async_process_audio_stream(metadata, _audio_stream())

        call_args = wrapped.async_process_audio_stream.call_args
        forwarded_metadata = call_args[0][0]
        assert forwarded_metadata.language == "en-US"

    @pytest.mark.asyncio
    async def test_corrector_uses_original_locale(self, mock_hass):
        """Correction pipeline sees the original locale, not the remapped one."""
        entry = _make_config_entry(
            options={
                "language_config": {
                    "mandarin": {
                        "zh-tw": {"stt_language": "zh", "script_conversion": "s2tw"},
                    }
                }
            }
        )
        wrapped = _make_wrapped_entity(text="你好", supported_languages=["zh"])
        entity = CorrectedSTTEntity(mock_hass, entry)

        build_locale = None

        def capture_build_corrector(locale=None, cfg=None):
            nonlocal build_locale
            build_locale = locale
            corrector = MagicMock()
            corrector.diagnose.return_value = MagicMock(
                corrected="你好", original="你好", changes=[], candidates=[]
            )
            return corrector

        with (
            patch.object(entity, "_get_wrapped_entity", return_value=wrapped),
            patch.object(
                entity, "_build_corrector", side_effect=capture_build_corrector
            ),
            patch.object(entity, "_phrase_builder") as mock_pb,
        ):
            mock_pb.build = AsyncMock(return_value=[])
            metadata = MagicMock(language="zh-TW")
            metadata.format = "wav"
            metadata.codec = "pcm"
            metadata.bit_rate = 16
            metadata.sample_rate = 16000
            metadata.channel = 1
            await entity.async_process_audio_stream(metadata, _audio_stream())

        # Corrector is built with original locale "zh-TW", not remapped "zh"
        assert build_locale == "zh-TW"

    @pytest.mark.asyncio
    async def test_natively_supported_locale_not_remapped(self, mock_hass):
        """When locale is natively supported, stt_language mapping to itself doesn't remap."""
        entry = _make_config_entry(
            options={
                "language_config": {
                    "mandarin": {
                        "zh-tw": {"stt_language": "zh-TW"},
                    }
                }
            }
        )
        wrapped = _make_wrapped_entity(text="你好", supported_languages=["zh-TW"])
        entity = CorrectedSTTEntity(mock_hass, entry)

        entity._corrector = MagicMock()
        entity._corrector.diagnose.return_value = MagicMock(
            corrected="你好", original="你好", changes=[], candidates=[]
        )

        with (
            patch.object(entity, "_get_wrapped_entity", return_value=wrapped),
            patch.object(entity, "_phrase_builder") as mock_pb,
        ):
            mock_pb.build = AsyncMock(return_value=[])
            metadata = MagicMock(language="zh-TW")
            metadata.format = "wav"
            metadata.codec = "pcm"
            metadata.bit_rate = 16
            metadata.sample_rate = 16000
            metadata.channel = 1
            await entity.async_process_audio_stream(metadata, _audio_stream())

        call_args = wrapped.async_process_audio_stream.call_args
        forwarded_metadata = call_args[0][0]
        assert forwarded_metadata.language == "zh-TW"

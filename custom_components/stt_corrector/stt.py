"""STT Corrector proxy platform for Home Assistant."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterable
from typing import TYPE_CHECKING, Any

from homeassistant.components.stt import (
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .capture import capture_context_var, capture_device_from_stream
from .const import (
    CONF_LANGUAGE_CONFIG,
    CONF_STT_LANGUAGE,
    CONF_WRAPPED_ENTITY_ID,
    DOMAIN,
)
from .correction import (
    CorrectionMethod,
    CorrectionResult,
    DiagnosticResult,
    LanguageModuleRegistry,
    ReplacementProcessor,
    SimilarityProcessor,
    SpeechCorrector,
    TextProcessor,
)
from .correction.languages import normalize_locale
from .correction.types import CorrectionChange
from .correction_config import CorrectionConfig
from .models import CorrectionStats, STTCorrectorRuntimeData
from .phrase_builder import PhraseBuilder

if TYPE_CHECKING:
    from . import STTCorrectorConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: STTCorrectorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up STT Corrector proxy from a config entry."""
    async_add_entities([CorrectedSTTEntity(hass, config_entry)])


class CorrectedSTTEntity(SpeechToTextEntity):
    """Proxy STT entity that wraps another STT entity with correction."""

    has_entity_name = True

    def __init__(
        self, hass: HomeAssistant, config_entry: STTCorrectorConfigEntry
    ) -> None:
        self._hass = hass
        self._config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=config_entry.title,
            manufacturer="HASS Cortex",
            model="STT Corrector",
            entry_type=DeviceEntryType.SERVICE,
        )

        cfg = CorrectionConfig.from_options(config_entry.options)
        self._phrase_builder = PhraseBuilder(
            hass, cfg.custom_phrases, cfg.auto_collect_sources
        )
        self._corrector_locale: str | None = None
        self._corrector = self._build_corrector(cfg=cfg)
        self._wrapped_registry_unsub: Any = None

    @property
    def _options(self) -> dict[str, Any]:
        return self._config_entry.options

    @property
    def supported_languages(self) -> list[str]:
        wrapped = self._get_wrapped_entity()
        if wrapped is None:
            return []
        base = list(wrapped.supported_languages)
        normalized_base = {normalize_locale(lang) for lang in base}
        lang_config = self._options.get(CONF_LANGUAGE_CONFIG, {})
        # Iterate all registered modules — locales may not be in stored config yet
        for module in LanguageModuleRegistry.all_modules():
            module_cfg = lang_config.get(module.module_key(), {})
            for locale in module.locales():
                norm = normalize_locale(locale)
                if norm in normalized_base:
                    continue
                locale_cfg = module_cfg.get(norm, {})
                if CONF_STT_LANGUAGE in locale_cfg:
                    # Explicitly configured: "" means disabled, non-empty means mapped
                    stt_lang = locale_cfg[CONF_STT_LANGUAGE]
                    if not stt_lang:
                        continue
                else:
                    # Not configured yet: auto-compute default
                    stt_lang = module.default_stt_language(locale, base)
                    if not stt_lang:
                        continue
                base.append(locale)
                normalized_base.add(norm)
        return base

    def _get_mapped_stt_language(
        self, locale: str, available_languages: list[str]
    ) -> str | None:
        """Look up the STT language mapping for a locale.

        Args:
            locale: The requested locale (e.g., "zh-TW").
            available_languages: Languages the wrapped STT entity supports.

        Returns:
            The mapped STT language if different from the locale, or None.
        """
        normalized = normalize_locale(locale)
        lang_config = self._options.get(CONF_LANGUAGE_CONFIG, {})
        module = LanguageModuleRegistry.get_module_for_locale(locale)
        if module is None:
            return None
        module_cfg = lang_config.get(module.module_key(), {})
        locale_cfg = module_cfg.get(normalized, {})
        if CONF_STT_LANGUAGE in locale_cfg:
            stt_lang = locale_cfg[CONF_STT_LANGUAGE]
        else:
            stt_lang = module.default_stt_language(locale, available_languages)
        if stt_lang and normalize_locale(stt_lang) != normalized:
            return stt_lang
        return None

    @property
    def supported_formats(self) -> list[Any]:
        wrapped = self._get_wrapped_entity()
        return wrapped.supported_formats if wrapped else []

    @property
    def supported_codecs(self) -> list[Any]:
        wrapped = self._get_wrapped_entity()
        return wrapped.supported_codecs if wrapped else []

    @property
    def supported_bit_rates(self) -> list[Any]:
        wrapped = self._get_wrapped_entity()
        return wrapped.supported_bit_rates if wrapped else []

    @property
    def supported_sample_rates(self) -> list[Any]:
        wrapped = self._get_wrapped_entity()
        return wrapped.supported_sample_rates if wrapped else []

    @property
    def supported_channels(self) -> list[Any]:
        wrapped = self._get_wrapped_entity()
        return wrapped.supported_channels if wrapped else []

    def _get_wrapped_entity(self) -> SpeechToTextEntity | None:
        from homeassistant.helpers import entity_registry as er

        wrapped_id = self._config_entry.data.get(CONF_WRAPPED_ENTITY_ID)
        if not wrapped_id:
            return None

        ent_reg = er.async_get(self._hass)
        entry = ent_reg.async_get(wrapped_id)
        if entry is None:
            _LOGGER.warning("Wrapped entity %s not found in registry", wrapped_id)
            return None

        # EntityComponent.entities returns dict_values, iterate directly
        entity_comp = self._hass.data.get("stt")
        if entity_comp is None:
            return None

        for platform_entity in getattr(entity_comp, "entities", []):
            if platform_entity.entity_id == entry.entity_id:
                return platform_entity

        _LOGGER.warning("Wrapped STT entity %s not loaded", entry.entity_id)
        return None

    async def async_added_to_hass(self) -> None:
        runtime_data: STTCorrectorRuntimeData = self._config_entry.runtime_data
        runtime_data.entity = self
        self._phrase_builder.async_start_listening()

        # Surface a fixable repair when the wrapped entity is gone, and
        # react live to it being removed/re-created in the registry.
        self._async_update_wrapped_entity_issue()
        wrapped_id = self._config_entry.data.get(CONF_WRAPPED_ENTITY_ID)
        if wrapped_id:
            from homeassistant.helpers.event import (
                async_track_entity_registry_updated_event,
            )

            self._wrapped_registry_unsub = async_track_entity_registry_updated_event(
                self._hass, wrapped_id, self._async_wrapped_registry_updated
            )

    async def async_will_remove_from_hass(self) -> None:
        self._phrase_builder.async_stop_listening()
        if self._wrapped_registry_unsub is not None:
            self._wrapped_registry_unsub()
            self._wrapped_registry_unsub = None

    @callback
    def _async_wrapped_registry_updated(self, _event: Any) -> None:
        """Registry changed for the wrapped entity — refresh the issue."""
        self._async_update_wrapped_entity_issue()

    @callback
    def _async_update_wrapped_entity_issue(self) -> None:
        """Create (or clear) the wrapped-entity-missing repair issue."""
        from homeassistant.helpers import entity_registry as er
        from homeassistant.helpers import issue_registry as ir

        from .repairs import wrapped_entity_issue_id

        wrapped_id = self._config_entry.data.get(CONF_WRAPPED_ENTITY_ID)
        missing = (
            not wrapped_id or er.async_get(self._hass).async_get(wrapped_id) is None
        )
        issue_id = wrapped_entity_issue_id(self._config_entry.entry_id)

        if missing:
            _LOGGER.warning(
                "Wrapped entity %s is gone; raising repair issue for %s",
                wrapped_id,
                self._config_entry.title,
            )
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="wrapped_entity_missing",
                translation_placeholders={
                    "title": self._config_entry.title,
                    "wrapped_entity_id": str(wrapped_id or ""),
                },
                data={"entry_id": self._config_entry.entry_id},
            )
        else:
            ir.async_delete_issue(self._hass, DOMAIN, issue_id)

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        # Identify the capture device BEFORE consuming the stream (the
        # original PipelineRun generator's frame is gone once exhausted),
        # and relay it to the wrapped entity via the shared ContextVar —
        # the replay generator below hides the run from downstream
        # introspection. Reset in `finally` so no value leaks past this
        # invocation.
        capture_device = capture_device_from_stream(self._hass, stream)
        capture_var = capture_context_var(self._hass)
        capture_token = capture_var.set(capture_device)
        try:
            return await self._process_audio_stream(metadata, stream, capture_device)
        finally:
            capture_var.reset(capture_token)

    async def _process_audio_stream(
        self,
        metadata: SpeechMetadata,
        stream: AsyncIterable[bytes],
        capture_device: str | None,
    ) -> SpeechResult:
        wrapped = self._get_wrapped_entity()
        if wrapped is None:
            self._push_stats(
                CorrectionStats(
                    result_state="wrapped_unavailable", capture_device=capture_device
                )
            )
            return SpeechResult(text=None, result=SpeechResultState.ERROR)

        audio_chunks: list[bytes] = []
        async for chunk in stream:
            audio_chunks.append(chunk)

        t0 = time.monotonic()

        async def replay() -> AsyncIterable[bytes]:
            for chunk in audio_chunks:
                yield chunk

        # Remap language if locale has an stt_language mapping
        mapped_lang = self._get_mapped_stt_language(
            metadata.language, wrapped.supported_languages
        )
        if mapped_lang is not None:
            forwarded_metadata = SpeechMetadata(
                language=mapped_lang,
                format=metadata.format,
                codec=metadata.codec,
                bit_rate=metadata.bit_rate,
                sample_rate=metadata.sample_rate,
                channel=metadata.channel,
            )
        else:
            forwarded_metadata = metadata

        result = await wrapped.async_process_audio_stream(forwarded_metadata, replay())

        if result.result == SpeechResultState.SUCCESS and result.text:
            if self._corrector_locale != metadata.language:
                self._corrector = self._build_corrector(locale=metadata.language)
                self._corrector_locale = metadata.language

            phrases = await self._phrase_builder.build()
            _LOGGER.debug("Phrase list: %d phrases", len(phrases))
            if _LOGGER.isEnabledFor(logging.DEBUG):
                for category, items in self._phrase_builder.categories.items():
                    if items:
                        _LOGGER.debug("  %s (%d): %s", category, len(items), items)
            cfg = CorrectionConfig.from_options(self._options)
            self._corrector.update_phrases(phrases)
            # diagnose() also materializes the fuzzy candidate scores for the DEBUG log; production
            # only needs the corrected text, so it takes the lighter correct().
            correction: CorrectionResult | DiagnosticResult = (
                self._corrector.diagnose(result.text)
                if _LOGGER.isEnabledFor(logging.DEBUG)
                else self._corrector.correct(result.text)
            )
            elapsed_ms = (time.monotonic() - t0) * 1000
            self._log_correction_result(correction, cfg)

            corrected_text = correction.corrected
            correction_applied = bool(correction.changes)

            self._push_stats(
                CorrectionStats(
                    result_state="success",
                    correction_applied=correction_applied,
                    language=metadata.language,
                    raw_text=result.text,
                    corrected_text=corrected_text if correction_applied else None,
                    processing_time_ms=elapsed_ms,
                    capture_device=capture_device,
                )
            )

            return SpeechResult(
                text=corrected_text,
                result=SpeechResultState.SUCCESS,
            )

        result_state = (
            "error" if result.result != SpeechResultState.SUCCESS else "no_speech"
        )

        self._push_stats(
            CorrectionStats(
                result_state=result_state,
                language=metadata.language,
                capture_device=capture_device,
            )
        )
        return result

    async def async_test_correction(self, text: str) -> Any:
        phrases = await self._phrase_builder.build()
        self._corrector.update_phrases(phrases)
        return self._corrector.diagnose(text)

    async def async_get_phrases(self) -> list[str]:
        return await self._phrase_builder.build()

    def rebuild_from_options(self) -> None:
        cfg = CorrectionConfig.from_options(self._options)
        self._corrector = self._build_corrector(locale=self._corrector_locale, cfg=cfg)
        self._phrase_builder.update_custom_phrases(cfg.custom_phrases)
        self._phrase_builder.update_sources(cfg.auto_collect_sources)

    def _log_correction_result(
        self,
        correction: CorrectionResult | DiagnosticResult,
        cfg: CorrectionConfig,
    ) -> None:
        """Log correction pipeline results at appropriate levels."""
        if correction.corrected != correction.original:
            _LOGGER.info(
                "Corrected: '%s' → '%s'",
                correction.original,
                correction.corrected,
            )

        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return

        # Only diagnose() (the DEBUG path) carries candidates; correct() (production) does not.
        # We only reach here with DEBUG on, so a diagnose() result is expected — default to [].
        candidates = getattr(correction, "candidates", [])

        # Partition changes by method

        lang_changes: list[CorrectionChange] = []
        custom_changes: list[CorrectionChange] = []
        fuzzy_changes: list[CorrectionChange] = []
        for change in correction.changes:
            if change.method in (
                CorrectionMethod.SCRIPT_CONVERSION,
                CorrectionMethod.PUNCTUATION_STRIP,
            ):
                lang_changes.append(change)
            elif change.method == CorrectionMethod.CUSTOM_RULE:
                custom_changes.append(change)
            else:
                fuzzy_changes.append(change)

        _LOGGER.debug(
            "Correction [language_processing]: %s, %d applied",
            "ON" if cfg.enable_language_processing else "OFF",
            len(lang_changes),
        )
        for change in lang_changes:
            _LOGGER.debug(
                "  [%s] '%s' → '%s'",
                change.method,
                change.original_segment,
                change.corrected_segment,
            )

        _LOGGER.debug(
            "Correction [replacements]: %s, %d rules, %d applied",
            "ON" if cfg.enable_custom_replacements else "OFF",
            len(cfg.custom_replacements),
            len(custom_changes),
        )
        for change in custom_changes:
            _LOGGER.debug(
                "  [custom_rule] '%s' → '%s'",
                change.original_segment,
                change.corrected_segment,
            )

        excluded_count = sum(1 for c in candidates if c.excluded)
        _LOGGER.debug(
            "Correction [similarity]: %s, threshold=%.2f, %d applied, %d exclusions (%d hit)",
            "ON" if cfg.enable_fuzzy_matching else "OFF",
            cfg.fuzzy_threshold,
            len(fuzzy_changes),
            len(cfg.custom_exclusions),
            excluded_count,
        )
        for change in fuzzy_changes:
            _LOGGER.debug(
                "  [fuzzy_match] '%s' → '%s' (score: %.2f)",
                change.original_segment,
                change.corrected_segment,
                change.confidence,
            )

        if candidates:
            top3 = candidates[:3]
            _LOGGER.debug("Top candidates:")
            for c in top3:
                status = (
                    "excluded"
                    if c.excluded
                    else "accepted"
                    if c.accepted
                    else "rejected"
                )
                _LOGGER.debug(
                    "  '%s' → '%s' (score: %.4f, threshold: %.2f, %s)",
                    c.segment,
                    c.phrase,
                    c.score,
                    c.threshold,
                    status,
                )

    def _build_corrector(
        self,
        locale: str | None = None,
        cfg: CorrectionConfig | None = None,
    ) -> SpeechCorrector:
        if cfg is None:
            cfg = CorrectionConfig.from_options(self._options)

        processors: list[TextProcessor] = []

        # Language Processing processors (only when locale is known)
        if cfg.enable_language_processing and locale:
            module = LanguageModuleRegistry.get_module_for_locale(locale)
            if module is not None:
                module_cfg = cfg.language_config.get(
                    module.module_key(), module.default_config()
                )
                processors.extend(module.get_processors(locale, module_cfg))

        # Custom Replacements processor
        if cfg.enable_custom_replacements and cfg.custom_replacements:
            processors.append(ReplacementProcessor(cfg.custom_replacements))

        # Similarity Matching processor
        if cfg.enable_fuzzy_matching:
            matchers = LanguageModuleRegistry.get_matchers(
                locale, language_config=cfg.language_config or None
            )
            processors.append(
                SimilarityProcessor(
                    known_phrases=[],
                    threshold=cfg.fuzzy_threshold,
                    matchers=matchers,
                    exclusions=cfg.custom_exclusions or None,
                )
            )

        return SpeechCorrector(processors)

    def _push_stats(self, stats: CorrectionStats) -> None:
        runtime_data: STTCorrectorRuntimeData = self._config_entry.runtime_data
        for sensor in runtime_data.sensors:
            sensor.handle_transcription(stats)

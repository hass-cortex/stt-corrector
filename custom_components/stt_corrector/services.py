"""Service handlers for STT Corrector integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError

from .const import (
    CONF_ACTIVE_PROCESSORS,
    CONF_AUTO_COLLECT_SOURCES,
    CONF_CUSTOM_EXCLUSIONS,
    CONF_CUSTOM_PHRASES,
    CONF_CUSTOM_REPLACEMENTS,
    CONF_FUZZY_THRESHOLD,
    CONF_LANGUAGE_CONFIG,
    CORRECTION_PROCESSOR_LANGUAGE,
    CORRECTION_PROCESSOR_REPLACEMENTS,
    CORRECTION_PROCESSOR_SIMILARITY,
    DOMAIN,
)
from .correction_config import CorrectionConfig

if TYPE_CHECKING:
    from .stt import CorrectedSTTEntity

_LOGGER = logging.getLogger(__name__)

# Input limits
MAX_REPLACEMENT_RULES = 100
MAX_PHRASE_LIST_SIZE = 500

# Service schemas — all require entity_id to target a specific instance
SCHEMA_PHRASES = vol.Schema(
    {
        vol.Required("entity_id"): str,
        vol.Required("phrases"): [str],
    }
)

SCHEMA_ADD_REPLACEMENTS = vol.Schema(
    {
        vol.Required("entity_id"): str,
        vol.Required("replacements"): {str: str},
    }
)

SCHEMA_REMOVE_REPLACEMENTS = vol.Schema(
    {
        vol.Required("entity_id"): str,
        vol.Required("keys"): [str],
    }
)

SCHEMA_SET_CORRECTION_CONFIG = vol.Schema(
    {
        vol.Required("entity_id"): str,
        vol.Optional("custom_phrases"): [str],
        vol.Optional("custom_replacements"): {str: str},
        vol.Optional("enable_language_processing"): bool,
        vol.Optional("enable_custom_replacements"): bool,
        vol.Optional("enable_fuzzy_matching"): bool,
        vol.Optional("fuzzy_threshold"): vol.All(
            vol.Coerce(float), vol.Range(min=0.5, max=1.0)
        ),
        vol.Optional("custom_exclusions"): [str],
        vol.Optional("auto_collect_sources"): [str],
        vol.Optional("language_config"): {str: {str: dict}},
    }
)

SCHEMA_GET_CORRECTION_CONFIG = vol.Schema(
    {
        vol.Required("entity_id"): str,
    }
)

SCHEMA_COPY_CORRECTION_CONFIG = vol.Schema(
    {
        vol.Required("source_entity_id"): str,
        vol.Required("target_entity_id"): vol.Any(str, [str]),
    }
)

SCHEMA_EXCLUSIONS = vol.Schema(
    {
        vol.Required("entity_id"): str,
        vol.Required("exclusions"): [str],
    }
)

SCHEMA_TEST_CORRECTION = vol.Schema(
    {
        vol.Required("entity_id"): str,
        vol.Required("text"): str,
    }
)


def _find_stt_entity(hass: HomeAssistant, entity_id: str) -> CorrectedSTTEntity:
    """Find a CorrectedSTTEntity by entity_id.

    Args:
        hass: Home Assistant instance.
        entity_id: The entity_id of the target STT Corrector entity.

    Raises:
        ServiceValidationError: If no matching entity is found.
    """
    from .models import STTCorrectorRuntimeData

    for cfg_entry in hass.config_entries.async_entries(DOMAIN):
        runtime_data = getattr(cfg_entry, "runtime_data", None)
        if (
            isinstance(runtime_data, STTCorrectorRuntimeData)
            and runtime_data.entity.entity_id == entity_id
        ):
            return runtime_data.entity
    raise ServiceValidationError(
        f"No {DOMAIN} STT entity found with entity_id '{entity_id}'.",
        translation_domain=DOMAIN,
        translation_key="entity_not_found",
    )


def _get_config_entry(hass: HomeAssistant, entity_id: str) -> ConfigEntry:
    """Get a STT Corrector config entry by entity_id.

    Args:
        hass: Home Assistant instance.
        entity_id: The entity_id of the target STT Corrector entity.

    Raises:
        ServiceValidationError: If no matching config entry is found.
    """
    from .models import STTCorrectorRuntimeData

    for cfg_entry in hass.config_entries.async_entries(DOMAIN):
        runtime_data = getattr(cfg_entry, "runtime_data", None)
        if (
            isinstance(runtime_data, STTCorrectorRuntimeData)
            and runtime_data.entity.entity_id == entity_id
        ):
            return cfg_entry
    raise ServiceValidationError(
        f"No {DOMAIN} config entry found for entity_id '{entity_id}'.",
        translation_domain=DOMAIN,
        translation_key="config_entry_not_found",
    )


async def _update_options(
    hass: HomeAssistant, new_options: dict[str, Any], entity_id: str
) -> None:
    """Persist updated options to the config entry."""
    entry = _get_config_entry(hass, entity_id)
    hass.config_entries.async_update_entry(entry, options=new_options)


async def async_handle_test_correction(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any]:
    """Run correction pipeline with diagnostic output."""
    text = call.data.get("text", "")
    if not text:
        raise ServiceValidationError(
            "text is required and cannot be empty",
            translation_domain=DOMAIN,
            translation_key="text_required",
        )

    entity = _find_stt_entity(hass, call.data["entity_id"])

    result = await entity.async_test_correction(text)
    return {
        "original": result.original,
        "corrected": result.corrected,
        "changes": [
            {
                "original_segment": c.original_segment,
                "corrected_segment": c.corrected_segment,
                "method": c.method,
                "confidence": c.confidence,
            }
            for c in result.changes
        ],
        "candidates": [
            {
                "phrase": c.phrase,
                "segment": c.segment,
                "score": c.score,
                "threshold": c.threshold,
                "accepted": c.accepted,
                "excluded": c.excluded,
            }
            for c in result.candidates
        ],
    }


async def async_handle_add_phrases(hass: HomeAssistant, call: ServiceCall) -> None:
    """Add phrases to the custom phrases list (deduplicated)."""
    entity_id: str = call.data["entity_id"]
    phrases_to_add: list[str] = call.data.get("phrases", [])
    if not phrases_to_add:
        return

    entry = _get_config_entry(hass, entity_id)
    current: list[str] = list(entry.options.get(CONF_CUSTOM_PHRASES, []))

    if len(current) + len(phrases_to_add) > MAX_PHRASE_LIST_SIZE:
        raise ServiceValidationError(
            f"Phrase list would exceed maximum size of {MAX_PHRASE_LIST_SIZE}",
            translation_domain=DOMAIN,
            translation_key="phrase_list_exceeded",
        )
    current_set = set(current)

    for phrase in phrases_to_add:
        phrase = phrase.strip()
        if phrase and phrase not in current_set:
            current.append(phrase)
            current_set.add(phrase)

    new_options = dict(entry.options) | {CONF_CUSTOM_PHRASES: current}
    await _update_options(hass, new_options, entity_id)


async def async_handle_remove_phrases(hass: HomeAssistant, call: ServiceCall) -> None:
    """Remove phrases from the custom phrases list."""
    entity_id: str = call.data["entity_id"]
    phrases_to_remove: list[str] = call.data.get("phrases", [])
    if not phrases_to_remove:
        return

    entry = _get_config_entry(hass, entity_id)
    remove_set = {p.strip() for p in phrases_to_remove}
    current: list[str] = list(entry.options.get(CONF_CUSTOM_PHRASES, []))
    updated = [p for p in current if p not in remove_set]

    new_options = dict(entry.options) | {CONF_CUSTOM_PHRASES: updated}
    await _update_options(hass, new_options, entity_id)


async def async_handle_add_replacements(hass: HomeAssistant, call: ServiceCall) -> None:
    """Add or update replacement rules (merged into existing)."""
    entity_id: str = call.data["entity_id"]
    replacements: dict[str, str] = call.data.get("replacements", {})
    if not replacements:
        return

    entry = _get_config_entry(hass, entity_id)
    current: dict[str, str] = dict(entry.options.get(CONF_CUSTOM_REPLACEMENTS, {}))

    merged_size = len(set(current) | set(replacements))
    if merged_size > MAX_REPLACEMENT_RULES:
        raise ServiceValidationError(
            f"Replacement rules would exceed maximum of {MAX_REPLACEMENT_RULES}",
            translation_domain=DOMAIN,
            translation_key="replacement_rules_exceeded",
        )

    current.update(replacements)

    new_options = dict(entry.options) | {CONF_CUSTOM_REPLACEMENTS: current}
    await _update_options(hass, new_options, entity_id)


async def async_handle_remove_replacements(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Remove replacement rules by key."""
    entity_id: str = call.data["entity_id"]
    keys: list[str] = call.data.get("keys", [])
    if not keys:
        return

    entry = _get_config_entry(hass, entity_id)
    current: dict[str, str] = dict(entry.options.get(CONF_CUSTOM_REPLACEMENTS, {}))
    for key in keys:
        current.pop(key.strip(), None)

    new_options = dict(entry.options) | {CONF_CUSTOM_REPLACEMENTS: current}
    await _update_options(hass, new_options, entity_id)


async def async_handle_add_exclusions(hass: HomeAssistant, call: ServiceCall) -> None:
    """Add segments to the exclusion list (deduplicated)."""
    entity_id: str = call.data["entity_id"]
    exclusions_to_add: list[str] = call.data.get("exclusions", [])
    if not exclusions_to_add:
        return

    entry = _get_config_entry(hass, entity_id)
    current: list[str] = list(entry.options.get(CONF_CUSTOM_EXCLUSIONS, []))
    current_set = set(current)

    for exc in exclusions_to_add:
        exc = exc.strip()
        if exc and exc not in current_set:
            current.append(exc)
            current_set.add(exc)

    new_options = dict(entry.options) | {CONF_CUSTOM_EXCLUSIONS: current}
    await _update_options(hass, new_options, entity_id)


async def async_handle_remove_exclusions(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Remove segments from the exclusion list."""
    entity_id: str = call.data["entity_id"]
    exclusions_to_remove: list[str] = call.data.get("exclusions", [])
    if not exclusions_to_remove:
        return

    entry = _get_config_entry(hass, entity_id)
    remove_set = {e.strip() for e in exclusions_to_remove}
    current: list[str] = list(entry.options.get(CONF_CUSTOM_EXCLUSIONS, []))
    updated = [e for e in current if e not in remove_set]

    new_options = dict(entry.options) | {CONF_CUSTOM_EXCLUSIONS: updated}
    await _update_options(hass, new_options, entity_id)


async def async_handle_get_correction_config(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any]:
    """Return the current correction configuration."""
    entry = _get_config_entry(hass, call.data["entity_id"])
    cfg = CorrectionConfig.from_options(entry.options)
    return {
        "custom_phrases": cfg.custom_phrases,
        "custom_replacements": cfg.custom_replacements,
        "enable_language_processing": cfg.enable_language_processing,
        "enable_custom_replacements": cfg.enable_custom_replacements,
        "enable_fuzzy_matching": cfg.enable_fuzzy_matching,
        "fuzzy_threshold": cfg.fuzzy_threshold,
        "custom_exclusions": cfg.custom_exclusions,
        "auto_collect_sources": cfg.auto_collect_sources,
        "language_config": cfg.language_config,
    }


async def async_handle_set_correction_config(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Replace the entire correction configuration."""
    data = dict(call.data)
    entity_id: str = data.pop("entity_id")
    entry = _get_config_entry(hass, entity_id)

    # Validate input limits
    if (
        "custom_replacements" in data
        and len(data["custom_replacements"]) > MAX_REPLACEMENT_RULES
    ):
        raise ServiceValidationError(
            f"Replacement rules would exceed maximum of {MAX_REPLACEMENT_RULES}",
            translation_domain=DOMAIN,
            translation_key="replacement_rules_exceeded",
        )
    if "custom_phrases" in data and len(data["custom_phrases"]) > MAX_PHRASE_LIST_SIZE:
        raise ServiceValidationError(
            f"Phrase list would exceed maximum size of {MAX_PHRASE_LIST_SIZE}",
            translation_domain=DOMAIN,
            translation_key="phrase_list_exceeded",
        )

    new_options = dict(entry.options)
    if "custom_phrases" in data:
        new_options[CONF_CUSTOM_PHRASES] = list(data["custom_phrases"])
    if "custom_replacements" in data:
        new_options[CONF_CUSTOM_REPLACEMENTS] = dict(data["custom_replacements"])
    processor_flags = {
        "enable_language_processing": CORRECTION_PROCESSOR_LANGUAGE,
        "enable_custom_replacements": CORRECTION_PROCESSOR_REPLACEMENTS,
        "enable_fuzzy_matching": CORRECTION_PROCESSOR_SIMILARITY,
    }
    if any(flag in data for flag in processor_flags):
        current = list(new_options.get(CONF_ACTIVE_PROCESSORS, []))
        for flag_key, processor in processor_flags.items():
            if flag_key in data:
                if data[flag_key] and processor not in current:
                    current.append(processor)
                elif not data[flag_key] and processor in current:
                    current.remove(processor)
        new_options[CONF_ACTIVE_PROCESSORS] = current
    if "fuzzy_threshold" in data:
        new_options[CONF_FUZZY_THRESHOLD] = float(data["fuzzy_threshold"])
    if "custom_exclusions" in data:
        new_options[CONF_CUSTOM_EXCLUSIONS] = list(data["custom_exclusions"])
    if "auto_collect_sources" in data:
        new_options[CONF_AUTO_COLLECT_SOURCES] = list(data["auto_collect_sources"])
    if "language_config" in data:
        new_options[CONF_LANGUAGE_CONFIG] = dict(data["language_config"])

    await _update_options(hass, new_options, entity_id)


async def async_handle_copy_correction_config(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Copy the full correction configuration to other correctors.

    The source's options (replacements, phrases, processors, thresholds,
    exclusions, auto-collect sources, language settings) replace each
    target's options wholesale. The wrapped entity is never touched.
    """
    source_id: str = call.data["source_entity_id"]
    targets = call.data["target_entity_id"]
    if isinstance(targets, str):
        targets = [targets]

    source_entry = _get_config_entry(hass, source_id)
    for target_id in targets:
        if target_id == source_id:
            raise ServiceValidationError(
                "source_entity_id and target_entity_id must differ",
                translation_domain=DOMAIN,
                translation_key="copy_source_is_target",
            )
        await _update_options(hass, dict(source_entry.options), target_id)
        _LOGGER.info("Copied correction config from %s to %s", source_id, target_id)


def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services.

    Uses async closures (not lambdas) so HA recognizes them as
    coroutine functions and properly awaits their return values.
    """

    async def _add_phrases(call: ServiceCall) -> None:
        await async_handle_add_phrases(hass, call)

    async def _remove_phrases(call: ServiceCall) -> None:
        await async_handle_remove_phrases(hass, call)

    async def _add_replacements(call: ServiceCall) -> None:
        await async_handle_add_replacements(hass, call)

    async def _remove_replacements(call: ServiceCall) -> None:
        await async_handle_remove_replacements(hass, call)

    async def _get_correction_config(call: ServiceCall) -> dict[str, Any]:
        return await async_handle_get_correction_config(hass, call)

    async def _set_correction_config(call: ServiceCall) -> None:
        await async_handle_set_correction_config(hass, call)

    async def _test_correction(call: ServiceCall) -> dict[str, Any]:
        return await async_handle_test_correction(hass, call)

    async def _add_exclusions(call: ServiceCall) -> None:
        await async_handle_add_exclusions(hass, call)

    async def _remove_exclusions(call: ServiceCall) -> None:
        await async_handle_remove_exclusions(hass, call)

    async def _copy_correction_config(call: ServiceCall) -> None:
        await async_handle_copy_correction_config(hass, call)

    hass.services.async_register(
        DOMAIN, "add_phrases", _add_phrases, schema=SCHEMA_PHRASES
    )
    hass.services.async_register(
        DOMAIN,
        "copy_correction_config",
        _copy_correction_config,
        schema=SCHEMA_COPY_CORRECTION_CONFIG,
    )
    hass.services.async_register(
        DOMAIN, "remove_phrases", _remove_phrases, schema=SCHEMA_PHRASES
    )
    hass.services.async_register(
        DOMAIN, "add_replacements", _add_replacements, schema=SCHEMA_ADD_REPLACEMENTS
    )
    hass.services.async_register(
        DOMAIN,
        "remove_replacements",
        _remove_replacements,
        schema=SCHEMA_REMOVE_REPLACEMENTS,
    )
    hass.services.async_register(
        DOMAIN,
        "get_correction_config",
        _get_correction_config,
        schema=SCHEMA_GET_CORRECTION_CONFIG,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "set_correction_config",
        _set_correction_config,
        schema=SCHEMA_SET_CORRECTION_CONFIG,
    )
    hass.services.async_register(
        DOMAIN,
        "test_correction",
        _test_correction,
        schema=SCHEMA_TEST_CORRECTION,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "add_exclusions", _add_exclusions, schema=SCHEMA_EXCLUSIONS
    )
    hass.services.async_register(
        DOMAIN, "remove_exclusions", _remove_exclusions, schema=SCHEMA_EXCLUSIONS
    )

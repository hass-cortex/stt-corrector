"""Service handlers for STT Corrector integration."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.components import persistent_notification
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
from .mishearing import FixPlan

if TYPE_CHECKING:
    from .recognition_log import Recognition
    from .stt import CorrectedSTTEntity

_LOGGER = logging.getLogger(__name__)

# Input limits
MAX_REPLACEMENT_RULES = 100
MAX_PHRASE_LIST_SIZE = 500

# Service schemas — all require entity_id to target a specific instance
SCHEMA_PHRASES = probatio.Schema(
    {
        probatio.Required("entity_id"): str,
        probatio.Required("phrases"): [str],
    }
)

SCHEMA_ADD_REPLACEMENTS = probatio.Schema(
    {
        probatio.Required("entity_id"): str,
        probatio.Required("replacements"): {str: str},
    }
)

SCHEMA_REMOVE_REPLACEMENTS = probatio.Schema(
    {
        probatio.Required("entity_id"): str,
        probatio.Required("keys"): [str],
    }
)

SCHEMA_SET_CORRECTION_CONFIG = probatio.Schema(
    {
        probatio.Required("entity_id"): str,
        probatio.Optional("custom_phrases"): [str],
        probatio.Optional("custom_replacements"): {str: str},
        probatio.Optional("enable_language_processing"): bool,
        probatio.Optional("enable_custom_replacements"): bool,
        probatio.Optional("enable_fuzzy_matching"): bool,
        probatio.Optional("fuzzy_threshold"): probatio.All(
            probatio.Coerce(float), probatio.Range(min=0.5, max=1.0)
        ),
        probatio.Optional("custom_exclusions"): [str],
        probatio.Optional("auto_collect_sources"): [str],
        probatio.Optional("language_config"): {str: {str: dict}},
    }
)

SCHEMA_GET_CORRECTION_CONFIG = probatio.Schema(
    {
        probatio.Required("entity_id"): str,
    }
)

SCHEMA_COPY_CORRECTION_CONFIG = probatio.Schema(
    {
        probatio.Required("source_entity_id"): str,
        probatio.Required("target_entity_id"): probatio.Any(str, [str]),
    }
)

SCHEMA_EXCLUSIONS = probatio.Schema(
    {
        probatio.Required("entity_id"): str,
        probatio.Required("exclusions"): [str],
    }
)

SCHEMA_REPORT_MISHEARING = probatio.Schema(
    {
        probatio.Required("heard"): str,
        probatio.Required("meant"): str,
        probatio.Optional("entity_id"): str,
        probatio.Optional("language"): str,
        probatio.Optional("dry_run", default=False): bool,
    }
)

EVENT_CORRECTION_LEARNED = f"{DOMAIN}_correction_learned"
EVENT_CORRECTION_PROPOSED = f"{DOMAIN}_correction_proposed"

SCHEMA_TEST_CORRECTION = probatio.Schema(
    {
        probatio.Required("entity_id"): str,
        probatio.Required("text"): str,
        probatio.Optional("language"): str,
    }
)


def _all_stt_entities(hass: HomeAssistant) -> list[CorrectedSTTEntity]:
    """Every loaded STT Corrector entity."""
    from .models import STTCorrectorRuntimeData

    return [
        runtime_data.entity
        for cfg_entry in hass.config_entries.async_entries(DOMAIN)
        if isinstance(
            runtime_data := getattr(cfg_entry, "runtime_data", None),
            STTCorrectorRuntimeData,
        )
        and runtime_data.entity is not None
    ]


def _find_stt_entity(hass: HomeAssistant, entity_id: str) -> CorrectedSTTEntity:
    """Find a CorrectedSTTEntity by entity_id.

    Args:
        hass: Home Assistant instance.
        entity_id: The entity_id of the target STT Corrector entity.

    Raises:
        ServiceValidationError: If no matching entity is found.
    """
    for entity in _all_stt_entities(hass):
        if entity.entity_id == entity_id:
            return entity
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

    language = call.data.get("language") or None
    result = await entity.async_test_correction(text, language)
    return {
        "locale": language or entity.correction_locale,
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


async def async_handle_report_mishearing(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any]:
    """Learn a validated fix from "STT heard X, the user meant Y"."""
    heard: str = call.data["heard"].strip()
    meant: str = call.data["meant"].strip()
    if not heard or not meant:
        raise ServiceValidationError(
            "heard and meant are required and cannot be empty",
            translation_domain=DOMAIN,
            translation_key="mishearing_text_required",
        )

    entity, recognition = _find_recognition(hass, heard, call.data.get("entity_id"))
    locale = (
        call.data.get("language")
        or (recognition.locale if recognition else None)
        or entity.correction_locale
    )
    if not locale:
        raise ServiceValidationError(
            "language is required: the corrector has not heard this utterance",
            translation_domain=DOMAIN,
            translation_key="mishearing_language_required",
        )

    raw = recognition.raw if recognition else heard
    started = time.monotonic()
    plan = await entity.async_plan_mishearing_fix(raw, meant, locale)
    elapsed_ms = (time.monotonic() - started) * 1000
    dry_run: bool = call.data.get("dry_run", False)
    status = plan.status
    if plan.fix is not None and not dry_run:
        # A phrase only ever corrects toward a known name: learn it now. A
        # rule rewrites its text in every sentence: the user approves it.
        if plan.fix.kind == "phrase":
            await async_apply_learned_fix(hass, entity.entity_id, heard, meant, plan)
            status = "applied"
        else:
            _propose_rule(hass, entity, heard, meant, raw, locale, plan)
            status = "proposed"
    _LOGGER.info(
        "Mishearing '%s' -> '%s' on %s: %s %s (planned in %.0f ms)",
        heard,
        meant,
        entity.entity_id,
        status,
        plan.fix.describe() if plan.fix else plan.reason,
        elapsed_ms,
    )
    return {
        "status": status,
        "entity_id": entity.entity_id,
        "locale": locale,
        "raw": raw,
        "corrected": plan.corrected,
        "fix": (
            {"type": plan.fix.kind, "wrong": plan.fix.wrong, "right": plan.fix.right}
            if plan.fix
            else None
        ),
        "reason": plan.reason,
    }


def _find_recognition(
    hass: HomeAssistant, heard: str, entity_id: str | None
) -> tuple[CorrectedSTTEntity, Recognition | None]:
    """The corrector that heard ``heard`` and that recognition.

    With an entity_id the entity is fixed and the recognition optional;
    without one, the newest recognition across all correctors decides.
    """
    if entity_id:
        entity = _find_stt_entity(hass, entity_id)
        return entity, entity.recognitions.find(heard)
    matches = [
        (recognition, entity)
        for entity in _all_stt_entities(hass)
        if (recognition := entity.recognitions.find(heard)) is not None
    ]
    if not matches:
        raise ServiceValidationError(
            f"No STT Corrector recently heard '{heard}'; pass entity_id and language.",
            translation_domain=DOMAIN,
            translation_key="mishearing_not_found",
        )
    recognition, entity = max(matches, key=lambda match: match[0].at)
    return entity, recognition


async def async_apply_learned_fix(
    hass: HomeAssistant, entity_id: str, heard: str, meant: str, plan: FixPlan
) -> None:
    """Write a planned fix and tell the user, with how to undo it."""
    fix = plan.fix
    assert fix is not None
    if fix.kind == "phrase":
        await _add_custom_phrases(hass, entity_id, [fix.right])
    else:
        await _add_replacement_rules(hass, entity_id, {fix.wrong: fix.right})
    undo = (
        f"`{DOMAIN}.remove_phrases` with phrases: [{fix.right}]"
        if fix.kind == "phrase"
        else f"`{DOMAIN}.remove_replacements` with keys: [{fix.wrong}]"
    )
    persistent_notification.async_create(
        hass,
        f"Heard **{heard}**, meant **{meant}**: added {fix.describe()} to "
        f"`{entity_id}`.\n\nUndo: {undo}.",
        title="STT Corrector learned a correction",
        notification_id=f"{DOMAIN}_learned_{entity_id}_{fix.kind}_{fix.right}",
    )
    hass.bus.async_fire(
        EVENT_CORRECTION_LEARNED,
        {
            "entity_id": entity_id,
            "heard": heard,
            "meant": meant,
            "type": fix.kind,
            "wrong": fix.wrong,
            "right": fix.right,
        },
    )


def _propose_rule(
    hass: HomeAssistant,
    entity: CorrectedSTTEntity,
    heard: str,
    meant: str,
    raw: str,
    locale: str,
    plan: FixPlan,
) -> None:
    """Raise a fixable repair asking the user to approve a learned rule."""
    from homeassistant.helpers import issue_registry as ir

    from .repairs import ISSUE_LEARNED_RULE, learned_rule_issue_id

    fix = plan.fix
    assert fix is not None
    entry = entity.config_entry
    ir.async_create_issue(
        hass,
        DOMAIN,
        learned_rule_issue_id(entry.entry_id, fix.wrong),
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_LEARNED_RULE,
        translation_placeholders={
            "title": entry.title,
            "wrong": fix.wrong,
            "right": fix.right,
            "heard": heard,
            "meant": meant,
        },
        data={
            "entry_id": entry.entry_id,
            "heard": heard,
            "meant": meant,
            "raw": raw,
            "locale": locale,
            "wrong": fix.wrong,
            "right": fix.right,
        },
    )
    hass.bus.async_fire(
        EVENT_CORRECTION_PROPOSED,
        {
            "entity_id": entity.entity_id,
            "heard": heard,
            "meant": meant,
            "type": fix.kind,
            "wrong": fix.wrong,
            "right": fix.right,
        },
    )


async def async_handle_add_phrases(hass: HomeAssistant, call: ServiceCall) -> None:
    """Add phrases to the custom phrases list (deduplicated)."""
    await _add_custom_phrases(
        hass, call.data["entity_id"], call.data.get("phrases", [])
    )


async def _add_custom_phrases(
    hass: HomeAssistant, entity_id: str, phrases_to_add: list[str]
) -> None:
    """Append phrases to an entity's custom phrases (deduplicated)."""
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
    await _add_replacement_rules(
        hass, call.data["entity_id"], call.data.get("replacements", {})
    )


async def _add_replacement_rules(
    hass: HomeAssistant, entity_id: str, replacements: dict[str, str]
) -> None:
    """Merge replacement rules into an entity's rules."""
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

    async def _report_mishearing(call: ServiceCall) -> dict[str, Any]:
        return await async_handle_report_mishearing(hass, call)

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
        DOMAIN,
        "report_mishearing",
        _report_mishearing,
        schema=SCHEMA_REPORT_MISHEARING,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, "add_exclusions", _add_exclusions, schema=SCHEMA_EXCLUSIONS
    )
    hass.services.async_register(
        DOMAIN, "remove_exclusions", _remove_exclusions, schema=SCHEMA_EXCLUSIONS
    )

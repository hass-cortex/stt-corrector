"""Constants for STT Corrector integration."""

from __future__ import annotations

DOMAIN = "stt_corrector"

# Config entry data keys
CONF_WRAPPED_ENTITY_ID = "wrapped_entity_id"

# Options keys — correction pipeline
CONF_FUZZY_THRESHOLD = "fuzzy_threshold"
CONF_CUSTOM_PHRASES = "custom_phrases"
CONF_CUSTOM_REPLACEMENTS = "custom_replacements"
CONF_ENABLE_CUSTOM_REPLACEMENTS = "enable_custom_replacements"
CONF_ENABLE_FUZZY_MATCHING = "enable_fuzzy_matching"
CONF_CUSTOM_EXCLUSIONS = "custom_exclusions"
CONF_AUTO_COLLECT_SOURCES = "auto_collect_sources"
CONF_CORRECTION_STAGES = "correction_stages"

# Correction stages (no "hints" — that's Azure-specific)
CORRECTION_STAGE_REPLACEMENTS = "replacements"
CORRECTION_STAGE_SIMILARITY = "similarity"
DEFAULT_CORRECTION_STAGES: list[str] = [
    CORRECTION_STAGE_REPLACEMENTS,
    CORRECTION_STAGE_SIMILARITY,
]

# Config flow sections
CONF_SECTION_AUTO_COLLECT = "auto_collect"
CONF_SECTION_REPLACEMENTS = "replacements"
CONF_SECTION_SIMILARITY = "similarity"

# Auto-collect sources
AUTO_COLLECT_FLOORS = "floors"
AUTO_COLLECT_AREAS = "areas"
AUTO_COLLECT_DEVICES = "devices"
AUTO_COLLECT_ENTITIES = "entities"
DEFAULT_AUTO_COLLECT_SOURCES: list[str] = [
    AUTO_COLLECT_FLOORS,
    AUTO_COLLECT_AREAS,
    AUTO_COLLECT_DEVICES,
    AUTO_COLLECT_ENTITIES,
]

# Defaults
DEFAULT_FUZZY_THRESHOLD = 0.80
DEFAULT_ENABLE_CUSTOM_REPLACEMENTS = True
DEFAULT_ENABLE_FUZZY_MATCHING = True

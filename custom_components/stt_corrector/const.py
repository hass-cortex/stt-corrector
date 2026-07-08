"""Constants for STT Corrector integration."""

from __future__ import annotations

DOMAIN = "stt_corrector"

# Config entry data keys
CONF_COPY_FROM = "copy_from"
CONF_WRAPPED_ENTITY_ID = "wrapped_entity_id"

# Options keys — correction pipeline
CONF_FUZZY_THRESHOLD = "fuzzy_threshold"
CONF_CUSTOM_PHRASES = "custom_phrases"
CONF_CUSTOM_REPLACEMENTS = "custom_replacements"
CONF_CUSTOM_EXCLUSIONS = "custom_exclusions"
CONF_AUTO_COLLECT_SOURCES = "auto_collect_sources"
CONF_ACTIVE_PROCESSORS = "active_processors"
CONF_LANGUAGE_CONFIG = "language_config"
CONF_STT_LANGUAGE = "stt_language"

# Correction processors
CORRECTION_PROCESSOR_LANGUAGE = "language_processing"
CORRECTION_PROCESSOR_REPLACEMENTS = "replacements"
CORRECTION_PROCESSOR_SIMILARITY = "similarity"
DEFAULT_ACTIVE_PROCESSORS: list[str] = [
    CORRECTION_PROCESSOR_LANGUAGE,
    CORRECTION_PROCESSOR_REPLACEMENTS,
    CORRECTION_PROCESSOR_SIMILARITY,
]

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

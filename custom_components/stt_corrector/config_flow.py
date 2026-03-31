"""Config flow for STT Corrector integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import section
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    AUTO_COLLECT_AREAS,
    AUTO_COLLECT_DEVICES,
    AUTO_COLLECT_ENTITIES,
    AUTO_COLLECT_FLOORS,
    CONF_ACTIVE_PROCESSORS,
    CONF_AUTO_COLLECT_SOURCES,
    CONF_CUSTOM_EXCLUSIONS,
    CONF_CUSTOM_PHRASES,
    CONF_CUSTOM_REPLACEMENTS,
    CONF_FUZZY_THRESHOLD,
    CONF_LANGUAGE_CONFIG,
    CONF_WRAPPED_ENTITY_ID,
    CORRECTION_PROCESSOR_LANGUAGE,
    CORRECTION_PROCESSOR_REPLACEMENTS,
    CORRECTION_PROCESSOR_SIMILARITY,
    DEFAULT_ACTIVE_PROCESSORS,
    DEFAULT_AUTO_COLLECT_SOURCES,
    DEFAULT_FUZZY_THRESHOLD,
    DOMAIN,
)
from .correction.languages import normalize_locale
from .correction.languages.registry import LanguageModuleRegistry

_LOGGER = logging.getLogger(__name__)


def _get_stt_entities(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return a list of enabled STT entity options (excluding stt_corrector itself)."""
    ent_reg = er.async_get(hass)
    options: list[dict[str, str]] = []
    for entry in ent_reg.entities.values():
        if entry.domain != "stt":
            continue
        if entry.platform == DOMAIN:
            continue
        if entry.disabled_by is not None:
            continue
        state = hass.states.get(entry.entity_id)
        label = (
            state.attributes.get("friendly_name", entry.entity_id)
            if state is not None
            else entry.entity_id
        )
        options.append(SelectOptionDict(value=entry.entity_id, label=label))
    return options


class STTCorrectorConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for STT Corrector."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        stt_options = _get_stt_entities(self.hass)

        if not stt_options and user_input is None:
            return self.async_abort(reason="no_stt_entities")

        if user_input is not None:
            entity_id = user_input[CONF_WRAPPED_ENTITY_ID]
            await self.async_set_unique_id(entity_id)
            self._abort_if_unique_id_configured()

            state = self.hass.states.get(entity_id)
            friendly_name = (
                state.attributes.get("friendly_name", entity_id)
                if state is not None
                else entity_id
            )
            return self.async_create_entry(
                title=f"{friendly_name} Corrected",
                data={CONF_WRAPPED_ENTITY_ID: entity_id},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_WRAPPED_ENTITY_ID): SelectSelector(
                    SelectSelectorConfig(options=stt_options)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> STTCorrectorOptionsFlow:
        """Get the options flow handler."""
        return STTCorrectorOptionsFlow(config_entry)


class STTCorrectorOptionsFlow(OptionsFlow):
    """Handle menu-based options flow for STT Corrector."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    @property
    def _options(self) -> dict[str, Any]:
        return dict(self._config_entry.options)

    async def _save_and_return(self, updates: dict[str, Any]) -> ConfigFlowResult:
        """Save updates immediately and return to main menu."""
        merged = {**self._options, **updates}
        self.hass.config_entries.async_update_entry(self._config_entry, options=merged)
        return await self.async_step_init()

    # -- Main menu --

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "active_processors",
                "language_settings",
                "phrase_collection",
                "replacements",
                "similarity",
            ],
        )

    # -- Active Processors --

    async def async_step_active_processors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure active correction processors."""
        if user_input is not None:
            processors = user_input.get(CONF_ACTIVE_PROCESSORS) or []
            return await self._save_and_return({CONF_ACTIVE_PROCESSORS: processors})

        options = self._options
        current_processors = options.get(
            CONF_ACTIVE_PROCESSORS, DEFAULT_ACTIVE_PROCESSORS
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ACTIVE_PROCESSORS, default=DEFAULT_ACTIVE_PROCESSORS
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=CORRECTION_PROCESSOR_LANGUAGE,
                                label="Language Processing",
                            ),
                            SelectOptionDict(
                                value=CORRECTION_PROCESSOR_REPLACEMENTS,
                                label="Custom Replacements",
                            ),
                            SelectOptionDict(
                                value=CORRECTION_PROCESSOR_SIMILARITY,
                                label="Similarity Matching",
                            ),
                        ],
                        multiple=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="active_processors",
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_ACTIVE_PROCESSORS: current_processors}
            ),
        )

    # -- Language Settings (sub-menu) --

    async def async_step_language_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show language settings sub-menu."""
        menu_options = [
            f"lang_{m.module_key()}" for m in LanguageModuleRegistry.all_modules()
        ]
        menu_options.append("init")  # back to main menu
        return self.async_show_menu(
            step_id="language_settings",
            menu_options=menu_options,
        )

    async def async_step_lang_mandarin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure Chinese language settings."""
        return await self._handle_language_step("mandarin", user_input)

    async def _handle_language_step(
        self, module_key: str, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Generic handler for language module config steps."""
        module = LanguageModuleRegistry.get_module_by_key(module_key)
        if module is None:
            return await self.async_step_init()

        if user_input is not None:
            # Extract per-locale config from section data
            locale_config: dict[str, dict[str, Any]] = {}
            for locale in module.locales():
                section_key = normalize_locale(locale).replace("-", "_")
                section_data = user_input.get(section_key, {})
                locale_config[normalize_locale(locale)] = dict(section_data)

            lang_config = dict(self._options.get(CONF_LANGUAGE_CONFIG, {}))
            lang_config[module_key] = locale_config
            return await self._save_and_return({CONF_LANGUAGE_CONFIG: lang_config})

        # Build form with one collapsible section per locale
        options = self._options
        lang_config = options.get(CONF_LANGUAGE_CONFIG, {})
        module_config = lang_config.get(module_key, module.default_config())
        schema_def = module.config_schema()
        defaults = module.default_config()

        fields: dict[vol.Marker, Any] = {}
        suggested: dict[str, Any] = {}
        select_opts = module.select_options()

        for locale_lower, settings in schema_def.items():
            section_key = locale_lower.replace("-", "_")
            locale_cfg = module_config.get(locale_lower, {})
            locale_defaults = defaults.get(locale_lower, {})

            # Build inner section fields
            section_fields: dict[vol.Marker, Any] = {}
            section_suggested: dict[str, Any] = {}

            for setting in settings:
                default_val = locale_defaults.get(setting, False)
                current_val = locale_cfg.get(setting, default_val)
                section_suggested[setting] = current_val

                if setting in select_opts:
                    section_fields[vol.Optional(setting, default=default_val)] = (
                        SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    SelectOptionDict(value=o["value"], label=o["label"])
                                    for o in select_opts[setting]
                                ],
                                mode="dropdown",
                            )
                        )
                    )
                elif isinstance(default_val, bool):
                    section_fields[vol.Required(setting, default=default_val)] = bool
                elif isinstance(default_val, str):
                    section_fields[vol.Optional(setting, default=default_val)] = (
                        TextSelector(TextSelectorConfig())
                    )

            suggested[section_key] = section_suggested

            # Collapse section if all values match defaults
            has_changes = any(
                locale_cfg.get(s) != locale_defaults.get(s)
                for s in settings
                if s in locale_cfg
            )
            fields[vol.Optional(section_key)] = section(
                vol.Schema(section_fields),
                {"collapsed": not has_changes},
            )

        schema = vol.Schema(fields)
        return self.async_show_form(
            step_id=f"lang_{module_key}",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
        )

    # -- Phrase Collection --

    async def async_step_phrase_collection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure phrase collection sources."""
        if user_input is not None:
            return await self._save_and_return(
                {
                    CONF_AUTO_COLLECT_SOURCES: user_input.get(
                        CONF_AUTO_COLLECT_SOURCES, DEFAULT_AUTO_COLLECT_SOURCES
                    ),
                    CONF_CUSTOM_PHRASES: [
                        p.strip()
                        for p in (user_input.get(CONF_CUSTOM_PHRASES) or [])
                        if p.strip()
                    ],
                }
            )

        options = self._options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_AUTO_COLLECT_SOURCES, default=DEFAULT_AUTO_COLLECT_SOURCES
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=AUTO_COLLECT_FLOORS, label="Floors"),
                            SelectOptionDict(value=AUTO_COLLECT_AREAS, label="Areas"),
                            SelectOptionDict(
                                value=AUTO_COLLECT_DEVICES, label="Devices"
                            ),
                            SelectOptionDict(
                                value=AUTO_COLLECT_ENTITIES,
                                label="Exposed Entities",
                            ),
                        ],
                        multiple=True,
                    )
                ),
                vol.Optional(CONF_CUSTOM_PHRASES, default=[]): TextSelector(
                    TextSelectorConfig(multiple=True)
                ),
            }
        )

        return self.async_show_form(
            step_id="phrase_collection",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_AUTO_COLLECT_SOURCES: options.get(
                        CONF_AUTO_COLLECT_SOURCES, DEFAULT_AUTO_COLLECT_SOURCES
                    ),
                    CONF_CUSTOM_PHRASES: options.get(CONF_CUSTOM_PHRASES, []),
                },
            ),
        )

    # -- Custom Replacements --

    async def async_step_replacements(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure custom replacement rules."""
        if user_input is not None:
            replacements: dict[str, str] = {}
            for entry in user_input.get(CONF_CUSTOM_REPLACEMENTS) or []:
                entry = entry.strip()
                if "=" in entry:
                    wrong, correct = entry.split("=", 1)
                    wrong = wrong.strip()
                    correct = correct.strip()
                    if wrong and correct:
                        replacements[wrong] = correct
            return await self._save_and_return({CONF_CUSTOM_REPLACEMENTS: replacements})

        options = self._options
        current_replacements = options.get(CONF_CUSTOM_REPLACEMENTS, {})
        current_list = [f"{k}={v}" for k, v in current_replacements.items()]

        schema = vol.Schema(
            {
                vol.Optional(CONF_CUSTOM_REPLACEMENTS, default=[]): TextSelector(
                    TextSelectorConfig(multiple=True)
                ),
            }
        )

        return self.async_show_form(
            step_id="replacements",
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_CUSTOM_REPLACEMENTS: current_list}
            ),
        )

    # -- Similarity Matching --

    async def async_step_similarity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure similarity matching settings."""
        if user_input is not None:
            exclusions = [
                e.strip()
                for e in (user_input.get(CONF_CUSTOM_EXCLUSIONS) or [])
                if e.strip()
            ]
            return await self._save_and_return(
                {
                    CONF_FUZZY_THRESHOLD: user_input.get(
                        CONF_FUZZY_THRESHOLD, DEFAULT_FUZZY_THRESHOLD
                    ),
                    CONF_CUSTOM_EXCLUSIONS: exclusions,
                }
            )

        options = self._options
        schema = vol.Schema(
            {
                vol.Required(CONF_FUZZY_THRESHOLD): vol.All(
                    vol.Coerce(float), vol.Range(min=0.5, max=1.0)
                ),
                vol.Optional(CONF_CUSTOM_EXCLUSIONS, default=[]): TextSelector(
                    TextSelectorConfig(multiple=True)
                ),
            }
        )

        return self.async_show_form(
            step_id="similarity",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_FUZZY_THRESHOLD: options.get(
                        CONF_FUZZY_THRESHOLD, DEFAULT_FUZZY_THRESHOLD
                    ),
                    CONF_CUSTOM_EXCLUSIONS: options.get(CONF_CUSTOM_EXCLUSIONS, []),
                },
            ),
        )

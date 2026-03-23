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
    CONF_AUTO_COLLECT_SOURCES,
    CONF_CORRECTION_STAGES,
    CONF_CUSTOM_EXCLUSIONS,
    CONF_CUSTOM_PHRASES,
    CONF_CUSTOM_REPLACEMENTS,
    CONF_ENABLE_CUSTOM_REPLACEMENTS,
    CONF_ENABLE_FUZZY_MATCHING,
    CONF_FUZZY_THRESHOLD,
    CONF_SECTION_AUTO_COLLECT,
    CONF_SECTION_REPLACEMENTS,
    CONF_SECTION_SIMILARITY,
    CONF_WRAPPED_ENTITY_ID,
    CORRECTION_STAGE_REPLACEMENTS,
    CORRECTION_STAGE_SIMILARITY,
    DEFAULT_AUTO_COLLECT_SOURCES,
    DEFAULT_CORRECTION_STAGES,
    DEFAULT_ENABLE_CUSTOM_REPLACEMENTS,
    DEFAULT_ENABLE_FUZZY_MATCHING,
    DEFAULT_FUZZY_THRESHOLD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _get_stt_entities(hass: HomeAssistant) -> list[dict[str, str]]:
    """Return a list of enabled STT entity options (excluding stt_corrector itself).

    Args:
        hass: The Home Assistant instance.

    Returns:
        List of SelectOptionDict-compatible dicts with "value" and "label" keys.
    """
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
        """Handle the initial setup step.

        Presents a selector of available STT entities. If none are found, aborts.
        """
        stt_options = _get_stt_entities(self.hass)

        if not stt_options and user_input is None:
            return self.async_abort(reason="no_stt_entities")

        if user_input is not None:
            entity_id = user_input[CONF_WRAPPED_ENTITY_ID]

            # One wrapper per STT entity — use entity_id as unique_id
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
    """Handle options flow for STT Corrector (single page)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle all correction options in a single page."""
        if user_input is not None:
            # Correction stages multi-select
            stages = user_input.get(CONF_CORRECTION_STAGES) or []

            # Extract auto-collect sources from section
            s_ac = user_input.get(CONF_SECTION_AUTO_COLLECT, {})
            auto_collect_sources = s_ac.get(
                CONF_AUTO_COLLECT_SOURCES, DEFAULT_AUTO_COLLECT_SOURCES
            )

            # Extract replacements section
            s_rep = user_input.get(CONF_SECTION_REPLACEMENTS, {})
            # Parse "wrong=correct" entries from list
            replacements: dict[str, str] = {}
            for entry in s_rep.get(CONF_CUSTOM_REPLACEMENTS) or []:
                entry = entry.strip()
                if "=" in entry:
                    wrong, correct = entry.split("=", 1)
                    wrong = wrong.strip()
                    correct = correct.strip()
                    if wrong and correct:
                        replacements[wrong] = correct

            # Extract similarity section
            s_sim = user_input.get(CONF_SECTION_SIMILARITY, {})
            phrases = [
                p.strip() for p in (s_ac.get(CONF_CUSTOM_PHRASES) or []) if p.strip()
            ]
            # custom_phrases may also live at the top level of auto_collect section
            if not phrases:
                phrases = [
                    p.strip()
                    for p in (user_input.get(CONF_CUSTOM_PHRASES) or [])
                    if p.strip()
                ]

            exclusions = [
                e.strip()
                for e in (s_sim.get(CONF_CUSTOM_EXCLUSIONS) or [])
                if e.strip()
            ]
            fuzzy_threshold = s_sim.get(CONF_FUZZY_THRESHOLD, DEFAULT_FUZZY_THRESHOLD)

            return self.async_create_entry(
                title="",
                data={
                    CONF_AUTO_COLLECT_SOURCES: auto_collect_sources,
                    CONF_CORRECTION_STAGES: stages,
                    CONF_ENABLE_CUSTOM_REPLACEMENTS: (
                        CORRECTION_STAGE_REPLACEMENTS in stages
                    ),
                    CONF_ENABLE_FUZZY_MATCHING: (CORRECTION_STAGE_SIMILARITY in stages),
                    CONF_FUZZY_THRESHOLD: fuzzy_threshold,
                    CONF_CUSTOM_PHRASES: phrases,
                    CONF_CUSTOM_REPLACEMENTS: replacements,
                    CONF_CUSTOM_EXCLUSIONS: exclusions,
                },
            )

        options = dict(self._config_entry.options)

        # Prepare current replacements as "wrong=correct" list
        current_replacements = options.get(CONF_CUSTOM_REPLACEMENTS, {})
        current_replacements_list = [
            f"{k}={v}" for k, v in current_replacements.items()
        ]

        # Build correction_stages from individual enable flags (backward compat)
        current_stages = options.get(CONF_CORRECTION_STAGES)
        if current_stages is None:
            current_stages = []
            if options.get(
                CONF_ENABLE_CUSTOM_REPLACEMENTS, DEFAULT_ENABLE_CUSTOM_REPLACEMENTS
            ):
                current_stages.append(CORRECTION_STAGE_REPLACEMENTS)
            if options.get(CONF_ENABLE_FUZZY_MATCHING, DEFAULT_ENABLE_FUZZY_MATCHING):
                current_stages.append(CORRECTION_STAGE_SIMILARITY)

        suggested_values = {
            CONF_CORRECTION_STAGES: current_stages,
            CONF_SECTION_AUTO_COLLECT: {
                CONF_AUTO_COLLECT_SOURCES: options.get(
                    CONF_AUTO_COLLECT_SOURCES, DEFAULT_AUTO_COLLECT_SOURCES
                ),
                CONF_CUSTOM_PHRASES: options.get(CONF_CUSTOM_PHRASES, []),
            },
            CONF_SECTION_REPLACEMENTS: {
                CONF_CUSTOM_REPLACEMENTS: current_replacements_list,
            },
            CONF_SECTION_SIMILARITY: {
                CONF_FUZZY_THRESHOLD: options.get(
                    CONF_FUZZY_THRESHOLD, DEFAULT_FUZZY_THRESHOLD
                ),
                CONF_CUSTOM_EXCLUSIONS: options.get(CONF_CUSTOM_EXCLUSIONS, []),
            },
        }

        schema = vol.Schema(
            {
                # Correction pipeline stage selector
                vol.Required(
                    CONF_CORRECTION_STAGES, default=DEFAULT_CORRECTION_STAGES
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=CORRECTION_STAGE_REPLACEMENTS,
                                label="Custom Replacements",
                            ),
                            SelectOptionDict(
                                value=CORRECTION_STAGE_SIMILARITY,
                                label="Similarity Matching",
                            ),
                        ],
                        multiple=True,
                    )
                ),
                # Auto-collect phrase sources
                vol.Optional(CONF_SECTION_AUTO_COLLECT): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_AUTO_COLLECT_SOURCES,
                                default=DEFAULT_AUTO_COLLECT_SOURCES,
                            ): SelectSelector(
                                SelectSelectorConfig(
                                    options=[
                                        SelectOptionDict(
                                            value=AUTO_COLLECT_FLOORS,
                                            label="Floors",
                                        ),
                                        SelectOptionDict(
                                            value=AUTO_COLLECT_AREAS,
                                            label="Areas",
                                        ),
                                        SelectOptionDict(
                                            value=AUTO_COLLECT_DEVICES,
                                            label="Devices",
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
                    ),
                    {"collapsed": True},
                ),
                # Replacements section
                vol.Optional(CONF_SECTION_REPLACEMENTS): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_CUSTOM_REPLACEMENTS, default=[]
                            ): TextSelector(TextSelectorConfig(multiple=True)),
                        }
                    ),
                    {"collapsed": True},
                ),
                # Similarity section
                vol.Optional(CONF_SECTION_SIMILARITY): section(
                    vol.Schema(
                        {
                            vol.Required(CONF_FUZZY_THRESHOLD): vol.All(
                                vol.Coerce(float), vol.Range(min=0.5, max=1.0)
                            ),
                            vol.Optional(
                                CONF_CUSTOM_EXCLUSIONS, default=[]
                            ): TextSelector(TextSelectorConfig(multiple=True)),
                        }
                    ),
                    {"collapsed": True},
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggested_values),
        )

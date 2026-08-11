# AGENTS.md

Instructions for AI coding agents working on this repository.

## Project Overview

Home Assistant custom integration that wraps any STT entity with a three-processor post-recognition correction pipeline: Language Processing, Custom Replacements, and Similarity Matching (fuzzy/phonetic). Acts as a proxy -- audio goes through the wrapped STT entity unchanged, then the transcribed text is corrected. Single-package repo (not a monorepo). Distributed as a HACS custom integration.

## Tech Stack

- **Runtime**: Python 3.14+, pypinyin
- **Package manager**: `uv` (not pip)
- **Testing**: pytest, pytest-asyncio (asyncio_mode = "auto"), pytest-cov
- **Linting**: ruff (lint + format)
- **Type checking**: pyright (standard mode; `reportMissingImports = "none"` -- `homeassistant` is not installed)
- **Version management**: commitizen (`cz bump`)
- **CI**: GitHub Actions (lint, test, mypy, hassfest, lock-check)

## Architecture

```
custom_components/stt_corrector/
├── __init__.py          # Entry point: async_setup_entry, async_unload_entry, pypinyin preload
├── stt.py               # CorrectedSTTEntity -- proxy STT entity wrapping any HA STT provider
├── sensor.py            # 10 correction statistics sensors (RestoreSensor-based)
├── config_flow.py       # Setup (wrapped entity + optional settings template), reconfigure (swap source), options
├── repairs.py           # Fixable repair flow: pick a replacement when the wrapped entity is gone
├── correction_config.py # CorrectionConfig dataclass (no Azure-specific fields)
├── phrase_builder.py    # Collects names from HA registries (floors, areas, devices, exposed entities)
├── services.py          # 10 HA services with vol.Schema validation
├── capture.py           # Capture-device introspection (PipelineRun stream) + shared ContextVar relay to downstream STT
├── helpers.py           # find_corrected_stt_entity via runtime_data lookup
├── models.py            # STTCorrectorRuntimeData + CorrectionStats dataclasses
├── const.py             # Constants, defaults, config keys
├── correction/          # Internal correction library (language-agnostic pipeline)
│   ├── corrector.py       # SpeechCorrector -- orchestrates three-processor pipeline
│   ├── fuzzy_matcher.py   # FuzzyMatcher -- sliding window + similarity scoring
│   ├── matchers.py        # PhoneticMatcher ABC + DefaultMatcher (SequenceMatcher fallback)
│   ├── registry.py        # MatcherRegistry -- delegates to LanguageModuleRegistry
│   ├── types.py           # CorrectionMethod, CorrectionChange, CorrectionResult, DiagnosticResult
│   ├── processors/        # Language processors
│   │   ├── base.py          # LanguageProcessor ABC
│   │   └── punctuation.py   # TrailingPunctuationStripper
│   └── languages/
│       ├── __init__.py      # LanguageModule ABC + normalize_locale()
│       ├── registry.py      # LanguageModuleRegistry
│       └── mandarin.py      # MandarinModule + PinyinMatcher + ChineseScriptConverter (configurable OpenCC mode)
├── services.yaml        # Service UI definitions
├── strings.json         # UI strings (source of truth)
└── translations/en.json # English translations (must match strings.json)
```

### Key Design Patterns

- **Proxy STT entity**: `CorrectedSTTEntity` relays audio to the wrapped entity via HA internal API, then corrects the result. Does not modify the wrapped entity. Supported languages/formats/codecs are proxied from the wrapped entity.
- **Lazy audio relay**: the relay generator forwards chunks as the pipeline produces them — it must never drain the stream first. Buffering would hand the wrapped entity a burst, so a streaming-capable engine pays for chunked inference with no live speech to overlap it against (measured: ~1.25s vs ~0.1s end-of-speech-to-text on a streaming Parakeet/Nemotron model). The fresh generator, not the buffering, is what hides the `PipelineRun` frame from downstream `capture.py` introspection. Guarded by `test_relays_audio_lazily`.
- **Entity public API**: `last_recognition`, `async_test_correction()`, `async_get_phrases()` -- services use these instead of accessing private attributes.
- **runtime_data**: Uses typed `STTCorrectorRuntimeData` dataclass (in `models.py`). Access entity via `runtime_data.entity`, sensors via `runtime_data.sensors`. Use `helpers.find_corrected_stt_entity()` to retrieve the STT entity.
- **Sensor push updates**: STT entity calls `_notify_sensors()` after each proxy invocation. Sensors use `RestoreSensor` for state persistence across restarts.
- **Wrapped entity resolution**: Tracked by entity registry ID (not entity_id string) to survive entity_id renames.
- **Wrapped-entity lifecycle**: `async_step_reconfigure` swaps the source in place (entry_id, corrected entity unique_id/entity_id, and options all preserved, so voice pipelines keep working). If the wrapped entity disappears, `stt.py` raises a fixable repair issue (checked on add-to-hass and live via entity-registry events); the fix flow in `repairs.py` re-selects a source and self-clears.
- **Config reuse**: `copy_correction_config` service copies the full options wholesale from one corrector to others; the setup dialog offers a "Copy settings from" template selector for new entries.
- **Three-processor correction pipeline**: Language Processing (punctuation stripping, script conversion) → Custom Replacements → Similarity Matching. Processors are independently toggleable.
- **LanguageModule framework**: Each language is a self-contained module (`correction/languages/`) providing processors (Language Processing), matchers (Similarity Matching), config schema, select options for dropdown settings, and per-locale defaults. Add new languages by subclassing `LanguageModule` and registering in `LanguageModuleRegistry`.
- **Corrector lifecycle**: `SpeechCorrector` is rebuilt when the audio locale changes. Phrases are updated on the existing corrector before each correction.
- **Locale normalization**: Always use `normalize_locale()` from `correction.languages` when comparing or looking up locale codes. HA Voice Pipeline and different STT engines send locales in inconsistent formats (`zh-TW`, `zh_tw`, `zh_TW`, `zh-tw`). The normalizer lowercases and converts underscores to hyphens (`zh-tw`). All config keys use this normalized format.
- **PhoneticMatcher**: Abstract base with `supports()`, `similarity()`, `windows()`. Now provided by `LanguageModule.get_matcher()` rather than direct registry lookup.
- **PhraseBuilder**: Event-driven cache invalidation via entity/area/device/floor registry event subscriptions. Auto-collect sources (floors, areas, devices, exposed entities) are independently configurable via `CONF_AUTO_COLLECT_SOURCES`.

## Development Commands

```bash
uv sync                                    # Install all deps
uv run pytest tests/ -v                    # Run tests
uv run pytest tests/ --cov=custom_components --cov-report=term-missing  # Coverage
uv run ruff check .                        # Lint
uv run ruff format .                       # Format
uv run pyright                             # Type check
uv run cz bump                             # Version bump (auto from commits)
```

## Testing

- Tests mock the entire `homeassistant` module hierarchy via `tests/conftest.py` (`sys.modules` injection). Read `conftest.py` before writing tests.
- `SpeechResult`, `ConfigEntry`, `HomeAssistant` etc. are all mock classes -- not real HA types.
- Coverage threshold: 70% (`fail_under` in pyproject.toml).

## Conventions

- **Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`). Enforced by commitizen pre-commit hook. `feat!:` or `BREAKING CHANGE:` footer for breaking changes.
- **Versioning**: Semver. `major_version_zero = true` -- breaking changes bump MINOR during 0.x, not MAJOR. Pre-release uses PEP 440 format (`0.2.0b1`), not semver hyphen format (`0.2.0-beta.1`).
- **Release notes**: Auto-generated by GitHub when `release.yml` creates a release. No `CHANGELOG.md` maintained.
- **Releasing**: `cz bump` locally (updates `pyproject.toml` + `manifest.json`, creates commit + tag), sync `uv.lock`, push with `--follow-tags`. GitHub Actions creates the release automatically. See [Release Workflow](#release-workflow) for full steps.
- **Docstrings**: Google-style with Args/Returns/Raises sections.
- **Type annotations**: Required on all public functions (`disallow_untyped_defs = true`). Use `TYPE_CHECKING` guard for HA imports.
- **Translations**: `strings.json` is source of truth. `translations/en.json` must be kept in sync (currently byte-identical).

## Known Issues

- `homeassistant` is not installed as a dependency (it's mocked in tests), so pyright is configured with `reportMissingImports = "none"` and `reportMissingTypeStubs = "none"`. IDE setups (e.g. Pylance) may still surface those import warnings locally; suppress them per-workspace if noisy.

## Quality Scale

This integration targets HA Integration Quality Scale compliance:

- **Bronze**: Fully compliant (config-flow, runtime-data, unique-config-entry, test-before-setup, has-entity-name, entity-unique-id, entity-event-setup, docs)
- **Silver**: Fully compliant (config-entry-unloading, parallel-updates, entity-unavailable, action-exceptions, test-coverage)
- **Gold/Platinum**: Partial -- see implementation spec for gaps

## Release & Distribution

### Version Files

Version is tracked in three places, kept in sync by commitizen (`cz bump`):

| File | Field |
|------|-------|
| `pyproject.toml` | `[project] version` and `[tool.commitizen] version` |
| `custom_components/stt_corrector/manifest.json` | `version` |

### HACS Configuration

`hacs.json`:
- `name` -- display name in HACS UI
- `homeassistant` -- minimum HA version (currently `2026.3.0`, required for Python 3.14+)
- `render_readme` -- show README in HACS detail page

### Release Workflow

Local bump + push triggers GitHub Actions to create the release automatically.

```bash
# Bump version (commitizen reads conventional commits to determine increment)
uv run cz bump                    # auto-detect: feat->minor, fix->patch
uv run cz bump --increment minor  # force minor
uv run cz bump --prerelease beta  # beta release (e.g., 0.3.0b1)

# Push (triggers release.yml)
git push origin main --follow-tags
```

`cz bump` automatically: updates version in `pyproject.toml` + `manifest.json`, syncs `uv.lock` (via `pre_bump_hooks`), creates commit + annotated tag.

## Adding a New Language Module

To add language-specific processing for a new language, two files need changes:

### Step 1: Create the language module (`correction/languages/<language>.py`)

Subclass `LanguageModule` and implement all abstract methods. See `mandarin.py` as reference.

```python
"""<Language> processing module for STT correction."""

from __future__ import annotations
from typing import Any
from . import LanguageModule, normalize_locale
from ..matchers import PhoneticMatcher
from ..processors.base import LanguageProcessor

class <Language>Module(LanguageModule):
    def locales(self) -> tuple[str, ...]:
        return ("<locale-1>", "<locale-2>")

    def module_key(self) -> str:
        return "<language>"

    def menu_label(self) -> str:
        return "<Display Name>"

    def default_config(self) -> dict[str, dict[str, Any]]:
        return {"<locale-1>": {"<setting>": True}, ...}

    def get_processors(self, locale, config) -> list[LanguageProcessor]:
        normalized = normalize_locale(locale)
        locale_cfg = config.get(normalized, {})
        # Return processors based on locale_cfg settings
        return []

    def get_matcher(self, locale, config) -> PhoneticMatcher | None:
        normalized = normalize_locale(locale)
        locale_cfg = config.get(normalized, {})
        # Return matcher or None
        return None

    def config_schema(self) -> dict[str, list[str]]:
        return {"<locale-1>": ["<setting1>", "<setting2>"], ...}

    def select_options(self) -> dict[str, list[dict[str, str]]]:
        # Return dropdown options for settings, or empty dict
        return {}
```

### Step 2: Register in `correction/languages/registry.py`

Add one entry to `LanguageModuleRegistry._modules`:

```python
from .languages.<language> import <Language>Module

class LanguageModuleRegistry:
    _modules: list[LanguageModule] = [MandarinModule(), <Language>Module()]
```

### Step 3: Add config flow step + strings

1. Add `async_step_lang_<key>` method in `config_flow.py` (delegates to `_handle_language_step`)
2. Add strings for the new step in `strings.json` and `translations/en.json`

### What NOT to change

- `matchers.py` -- ABC and DefaultMatcher only
- `corrector.py`, `fuzzy_matcher.py` -- pipeline core, language-agnostic
- `stt.py` -- delegates to LanguageModuleRegistry, no language-specific knowledge

## Locale Handling

**CRITICAL:** Always use `normalize_locale()` from `correction.languages` when comparing or looking up locale codes.

HA Voice Pipeline and STT engines send locales in inconsistent formats:
- `zh-TW` (BCP-47 standard, hyphen, mixed case)
- `zh_TW` (underscore separator)
- `zh-tw` (lowercase)
- `zh_tw` (underscore + lowercase)

`normalize_locale()` converts all formats to lowercase with hyphen: `zh-tw`. All config keys and internal lookups use this normalized format.

**DO NOT** use `.lower()` alone -- it doesn't handle underscore separators.

### STT Language Mapping (`stt_language`)

Each locale in a language module can map to an underlying STT engine language via the `stt_language` config key. This is a **generic infrastructure feature** handled by `_handle_language_step()` in `config_flow.py` and `supported_languages` / `_get_mapped_stt_language()` in `stt.py` -- individual language modules do not need to implement anything.

**Three-state config logic** (in `stt.py:supported_languages` and `_get_mapped_stt_language`):
- **Key absent** (never configured): auto-compute default via `LanguageModule.default_stt_language()` (exact match → prefix match → empty)
- **Key = `""`** (explicitly disabled): locale is not advertised in `supported_languages`
- **Key = `"zh"`** (explicitly mapped): locale is advertised, audio forwarded with mapped language

**`default_stt_language()`** is a non-abstract method on `LanguageModule` with sensible defaults (exact match → prefix match → empty). Subclasses can override for language-specific heuristics.

**Config storage:** `stt_language` is stored alongside module-specific settings in `CONF_LANGUAGE_CONFIG[module_key][locale]` but is NOT part of the module's `config_schema()` or `_SETTINGS` -- it's injected generically by the config flow infrastructure.

## Documentation Updates

When adding features or changing behavior, update these files:

| File | What to update |
|------|---------------|
| `README.md` | Feature list, pipeline diagram, config options table, FAQ |
| `docs/correction-pipeline.md` | Pipeline processors, worked examples |
| `docs/sensors.md` | If adding/changing sensor entities |
| `docs/services.md` | If adding/changing services |
| `AGENTS.md` | Architecture section, adding language guide, conventions |
| `strings.json` + `translations/en.json` | UI strings (must be kept in sync) |

## Do NOT

- Access entity private attributes from `services.py` or `helpers.py` -- use public API methods
- Add `homeassistant` as a dependency in `pyproject.toml` -- it is mocked in tests
- Modify `translations/en.json` without updating `strings.json` (or vice versa)
- Create nested wrappers -- config flow filters out `stt_corrector` entities from the wrapped entity selector
- Track wrapped entity by entity_id string -- always use entity registry ID
- Add features without updating documentation (README.md, docs/, AGENTS.md)

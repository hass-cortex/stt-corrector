# AGENTS.md

Instructions for AI coding agents working on this repository.

## Project Overview

Home Assistant custom integration that wraps any STT entity with a two-stage post-recognition correction pipeline. Acts as a proxy -- audio goes through the wrapped STT entity unchanged, then the transcribed text is corrected using custom replacements and fuzzy/phonetic similarity matching. Single-package repo (not a monorepo). Distributed as a HACS custom integration.

## Tech Stack

- **Runtime**: Python 3.14+, pypinyin
- **Package manager**: `uv` (not pip)
- **Testing**: pytest, pytest-asyncio (asyncio_mode = "auto"), pytest-cov
- **Linting**: ruff (lint + format)
- **Type checking**: mypy (ignore_missing_imports = true -- `homeassistant` is not installed)
- **Version management**: commitizen (`cz bump`)
- **CI**: GitHub Actions (lint, test, mypy, hassfest, lock-check)

## Architecture

```
custom_components/stt_corrector/
├── __init__.py          # Entry point: async_setup_entry, async_unload_entry, pypinyin preload
├── stt.py               # CorrectedSTTEntity -- proxy STT entity wrapping any HA STT provider
├── sensor.py            # 7 correction statistics sensors (RestoreSensor-based)
├── config_flow.py       # Setup (select wrapped STT entity) + options (correction settings)
├── correction_config.py # CorrectionConfig dataclass (no Azure-specific fields)
├── phrase_builder.py    # Collects names from HA registries (floors, areas, devices, exposed entities)
├── services.py          # 9 HA services with vol.Schema validation
├── helpers.py           # find_corrected_stt_entity via runtime_data lookup
├── models.py            # STTCorrectorRuntimeData + CorrectionStats dataclasses
├── const.py             # Constants, defaults, config keys
├── correction/          # Internal correction library (language-agnostic pipeline)
│   ├── corrector.py       # SpeechCorrector -- orchestrates two-stage pipeline
│   ├── fuzzy_matcher.py   # FuzzyMatcher -- sliding window + similarity scoring
│   ├── matchers.py        # PhoneticMatcher ABC + DefaultMatcher (SequenceMatcher fallback)
│   ├── registry.py        # Locale-to-matcher mapping (add new languages here)
│   ├── types.py           # CorrectionMethod, CorrectionChange, CorrectionResult, DiagnosticResult
│   └── languages/
│       └── mandarin.py    # PinyinMatcher + syllable-level pinyin similarity
├── services.yaml        # Service UI definitions
├── strings.json         # UI strings (source of truth)
└── translations/en.json # English translations (must match strings.json)
```

### Key Design Patterns

- **Proxy STT entity**: `CorrectedSTTEntity` buffers audio, forwards to wrapped entity via HA internal API, then corrects the result. Does not modify the wrapped entity. Supported languages/formats/codecs are proxied from the wrapped entity.
- **Entity public API**: `last_recognition`, `async_test_correction()`, `async_get_phrases()` -- services use these instead of accessing private attributes.
- **runtime_data**: Uses typed `STTCorrectorRuntimeData` dataclass (in `models.py`). Access entity via `runtime_data.entity`, sensors via `runtime_data.sensors`. Use `helpers.find_corrected_stt_entity()` to retrieve the STT entity.
- **Sensor push updates**: STT entity calls `_notify_sensors()` after each proxy invocation. Sensors use `RestoreSensor` for state persistence across restarts.
- **Wrapped entity resolution**: Tracked by entity registry ID (not entity_id string) to survive entity_id renames.
- **Corrector lifecycle**: `SpeechCorrector` is rebuilt when the audio locale changes (different locale may require different phonetic matchers). Phrases are updated on the existing corrector before each correction.
- **PhoneticMatcher**: Abstract base with `supports()`, `similarity()`, `windows()`. Add new language matchers by subclassing in `correction/languages/` and registering in `registry.py` -- no core changes needed. See [Adding a New Language Matcher](#adding-a-new-language-matcher).
- **PhraseBuilder**: Event-driven cache invalidation via entity/area/device/floor registry event subscriptions. Auto-collect sources (floors, areas, devices, exposed entities) are independently configurable via `CONF_AUTO_COLLECT_SOURCES`.

## Development Commands

```bash
uv sync                                    # Install all deps
uv run pytest tests/ -v                    # Run tests
uv run pytest tests/ --cov=custom_components --cov-report=term-missing  # Coverage
uv run ruff check .                        # Lint
uv run ruff format .                       # Format
uv run mypy custom_components/             # Type check
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

- `ruff format` may have false positives on `config_flow.py` (removes parentheses from multi-except, invalid in Python 3). Exclude from ruff format in `pyproject.toml` if needed.
- Pyright reports many `reportMissingImports` because `homeassistant` is not installed. These are expected -- we use mypy with `ignore_missing_imports = true` instead.
- `list[DefaultMatcher]` vs `list[PhoneticMatcher]` type variance warning is a known Pyright/mypy limitation (list is invariant). Does not affect runtime.

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

## Adding a New Language Matcher

To add phonetic correction for a new language, only two files need changes:

### Step 1: Create the matcher (`correction/languages/<language>.py`)

Subclass `PhoneticMatcher` and implement three methods:

```python
"""<Language> phonetic matching for STT correction."""

from __future__ import annotations

from ..matchers import PhoneticMatcher


class <Language>Matcher(PhoneticMatcher):

    def supports(self, text: str) -> bool:
        """Return True if text contains characters this matcher handles."""

    def similarity(self, text_a: str, text_b: str) -> float:
        """Compute phonetic similarity (0.0-1.0) between two strings."""

    def windows(self, text: str, phrase: str) -> list[tuple[int, int]]:
        """Generate (start, end) sliding window positions for matching."""
```

| Method | Purpose | Example (Mandarin) |
|--------|---------|-------------------|
| `supports()` | Detect if text belongs to this language | CJK unicode range check |
| `similarity()` | Phonetic similarity score | Pinyin syllable comparison |
| `windows()` | Sliding window strategy | Character-level for CJK, word-level for alphabetic |

See `correction/languages/mandarin.py` as a reference implementation.

### Step 2: Register in `correction/registry.py`

Add one entry to `MatcherRegistry._language_matchers`:

```python
from .languages.<language> import <Language>Matcher

class MatcherRegistry:
    _language_matchers: list[tuple[tuple[str, ...], type[PhoneticMatcher]]] = [
        (("zh-CN", "zh-TW"), PinyinMatcher),
        (("ja",), <Language>Matcher),  # <-- add here
    ]
```

The tuple contains BCP-47 locale prefixes that activate this matcher. `DefaultMatcher` is always appended as fallback -- do not add it here.

### What NOT to change

- `matchers.py` -- ABC and DefaultMatcher only
- `corrector.py`, `fuzzy_matcher.py` -- pipeline core, language-agnostic
- `stt.py` -- delegates to registry, no matcher knowledge

## Do NOT

- Access entity private attributes from `services.py` or `helpers.py` -- use public API methods
- Add `homeassistant` as a dependency in `pyproject.toml` -- it is mocked in tests
- Modify `translations/en.json` without updating `strings.json` (or vice versa)
- Create nested wrappers -- config flow filters out `stt_corrector` entities from the wrapped entity selector
- Track wrapped entity by entity_id string -- always use entity registry ID

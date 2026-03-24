# Contributing to STT Corrector for Home Assistant

Thank you for considering contributing to this project. This guide covers the development setup, testing, and submission process.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager
- A Home Assistant instance (for integration testing)

## Development Setup

```bash
git clone https://github.com/hass-cortex/stt-corrector.git
cd stt-corrector
uv sync --group dev --group test
```

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage report
uv run pytest tests/ --cov=custom_components --cov-report=term-missing

# Run a specific test file
uv run pytest tests/test_stt.py -v
```

## Code Style

This project enforces consistent code style via automated tooling:

- **Linting**: `uv run ruff check .`
- **Formatting**: `uv run ruff format .`
- **Type checking**: `uv run mypy custom_components/`
- Follow Google-style docstrings for all public functions and classes

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use case |
|--------|----------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation only |
| `chore:` | Maintenance / tooling |
| `refactor:` | Code restructure without behavior change |
| `test:` | Adding or updating tests |

Example: `feat: add Japanese phonetic matcher`

## Submitting Changes

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes with appropriate tests
4. Ensure all checks pass (`ruff check`, `ruff format --check`, `pytest`)
5. Submit a pull request with a clear description of the change

## Project Structure

```
stt-corrector/
  custom_components/stt_corrector/
    __init__.py          # Integration setup (pypinyin preload, platform forwarding)
    stt.py               # Proxy STT entity (wraps any STT provider with correction)
    sensor.py            # Correction statistics sensors (RestoreSensor)
    models.py            # Runtime data models (STTCorrectorRuntimeData)
    config_flow.py       # Config flow (select wrapped STT entity) + options
    correction_config.py # CorrectionConfig dataclass
    helpers.py           # Entity lookup helpers
    phrase_builder.py    # HA registry phrase collection for fuzzy matching
    services.py          # HA service handlers
    const.py             # Constants, defaults, config keys
    correction/          # Language-agnostic correction pipeline
      corrector.py         # SpeechCorrector (two-stage pipeline)
      fuzzy_matcher.py     # Sliding window + similarity scoring
      matchers.py          # PhoneticMatcher ABC + DefaultMatcher
      registry.py          # Locale-to-matcher mapping
      languages/           # Language-specific matchers
        mandarin.py          # Pinyin-based phonetic matching
  tests/                 # Test suite
  pyproject.toml         # Project metadata and tool config
```

## Adding a New Language Matcher

See the [AGENTS.md](AGENTS.md#adding-a-new-language-matcher) for a step-by-step guide on adding phonetic correction for a new language.

## Reporting Issues

Please use GitHub Issues with the provided templates. Include:

- Home Assistant version
- Integration version
- Steps to reproduce
- Expected vs actual behavior
- Relevant debug logs (see README for how to enable debug logging)

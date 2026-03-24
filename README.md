# STT Corrector for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/hass-cortex/stt-corrector)](https://github.com/hass-cortex/stt-corrector/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-blue.svg)](https://hacs.xyz/)
[![HA Version](https://img.shields.io/badge/HA-2026.3.0+-green.svg)](https://www.home-assistant.io/)
[![GitHub License](https://img.shields.io/github/license/hass-cortex/stt-corrector)](https://github.com/hass-cortex/stt-corrector/blob/main/LICENSE)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/hass-cortex/stt-corrector)

A Home Assistant custom integration that wraps any STT (speech-to-text) entity with a post-recognition correction pipeline for improved voice command accuracy.

```
Audio --► Wrapped STT Entity --► Raw Text --► Custom Replacements --► Similarity Matching --► Final Text
          (Azure, Whisper,                       (Stage 1)               (Stage 2)
           Google, etc.)
```

| Stage | When | What |
|-------|------|------|
| **1. Custom Replacements** | After STT | User-defined `wrong=correct` substitution rules |
| **2. Similarity Matching** | After STT | Fuzzy/phonetic matching against known phrases (pinyin for Chinese) |

Each stage can be enabled/disabled independently.

## Features

- **Wraps any STT entity** -- Azure, Whisper, Google Cloud, or any other HA STT provider, without modifying it
- **Two-stage correction pipeline** -- custom replacements and fuzzy/phonetic similarity matching
- **Configurable auto-collect** -- independently toggle collection of exposed entities, devices, areas, and floor names from HA registries
- **Language-aware matching** -- pinyin for Mandarin Chinese, SequenceMatcher for other languages
- **Runtime statistics** -- 7 sensor entities tracking usage and correction performance ([details](docs/sensors.md))
- **Management services** -- 9 services for runtime configuration with entity targeting ([details](docs/services.md))
- **No external API dependencies** -- all correction happens locally using the wrapped entity's transcription output

## Getting Started

**Prerequisites:** Home Assistant **2026.3.0+** and at least one STT entity already configured (e.g., Whisper, Azure Speech-to-Text, Google Cloud STT).

### 1. Install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hass-cortex&repository=stt-corrector&category=integration)

Click the button above, or manually: HACS > three-dot menu > **Custom repositories** > add `https://github.com/hass-cortex/stt-corrector` (Integration) > install > restart HA.

<details>
<summary>Manual installation</summary>

Copy `custom_components/stt_corrector/` to your HA `config/custom_components/` directory, then restart.
</details>

### 2. Add Integration

[![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=stt_corrector)

Click the button above, or manually: **Settings > Devices & Services > Add Integration** > search "STT Corrector".

Select the STT entity you want to wrap (e.g., "Azure Speech-to-Text" or "Whisper"). The integration creates a new STT entity named "Corrected \<original name\>" that proxies audio through the original and applies corrections.

### 3. Assign to Voice Pipeline

[![Open your Home Assistant instance and manage your voice assistants.](https://my.home-assistant.io/badges/voice_assistants.svg)](https://my.home-assistant.io/redirect/voice_assistants/)

Select or create a voice pipeline, then set **Speech-to-text** to your new corrected STT entity.

### 4. (Optional) Configure Correction

[![Open your Home Assistant instance and show this integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=stt_corrector)

Configure via the integration page > **Configure**:

| Section | Option | Default | Description |
|---------|--------|---------|-------------|
| **Correction Stages** | Stages | Both enabled | Which correction stages to run |
| **Custom Replacements** | Replacements | Empty | `wrong=correct` substitution rules |
| **Similarity Matching** | Fuzzy threshold | 0.80 | Minimum similarity score (0.5-1.0) to accept a match |
| **Similarity Matching** | Exclusions | Empty | Text segments to never correct |
| **Phrase Sources** | Auto-collect sources | All enabled | Which HA registries to collect phrases from (floors, areas, devices, exposed entities) |
| **Phrase Sources** | Custom phrases | Empty | Additional phrases for similarity matching |

### Uninstallation

**Settings > Devices & Services** > STT Corrector > three-dot menu > **Delete** > remove `custom_components/stt_corrector/` > restart HA.

## Debugging

Enable debug logging to see detailed correction pipeline output:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.stt_corrector: debug
```

Use the `test_correction` service to test corrections without sending actual audio. This shows all fuzzy match candidates and their scores, helping you tune the threshold and identify phrases that need exclusion rules.

## FAQ

**Which STT providers can I wrap?**

Any Home Assistant STT entity -- Azure Speech-to-Text, Whisper, Google Cloud STT, or any other integration that creates an `stt.*` entity. The corrector does not modify the wrapped entity in any way.

**Can I wrap an already-wrapped entity?**

No. The config flow filters out other `stt_corrector` entities to prevent nesting. Each STT entity can only be wrapped once.

**Why is my transcription inaccurate?**

- Check that the correct language/locale is selected in your voice pipeline
- Add custom phrases for domain-specific words like device names
- Add replacement rules for consistently misrecognized words
- Lower the similarity threshold if fuzzy matching is not catching errors
- Use `test_correction` to diagnose which candidates are being considered

**What is pinyin matching?**

For Chinese (CJK) text, the integration converts characters to their romanized pronunciation (pinyin) and compares phonetic similarity at the syllable level. This handles cases where the STT engine recognizes a homophone instead of the intended word. Tone differences are tolerated with reduced confidence, and acoustically similar initials (e.g., l/r/n, zh/z, sh/s) receive partial credit.

**Can I use this without auto-collected phrases?**

Yes. Disable all auto-collect sources in the configuration options and only use custom phrases. Or disable similarity matching entirely and rely solely on custom replacements.

**How do I install the latest development version?**

After the integration is installed via HACS, you can switch to the latest `main` branch using the `update.install` action:

1. Go to **Developer Tools > Actions**
2. Select the `update.install` action
3. In **Target**, select the STT Corrector update entity (e.g., `update.stt_corrector_update`)
4. In **Version**, enter `main` (or a specific commit hash)
5. Click **Perform Action**
6. Restart HA

Development versions may contain breaking changes -- to revert, run the same action with a release tag (e.g., `0.2.0`).

## Documentation

| Document | Description |
|----------|-------------|
| [How It Works](docs/how-it-works.md) | Correction pipeline architecture and matching strategies |
| [Sensors](docs/sensors.md) | Sensor entities for correction tracking and monitoring |
| [Services](docs/services.md) | Management services with parameters and examples |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## License

[MIT](LICENSE)

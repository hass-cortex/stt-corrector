# STT Corrector for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/hass-cortex/stt-corrector)](https://github.com/hass-cortex/stt-corrector/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-blue.svg)](https://hacs.xyz/)
[![HA Version](https://img.shields.io/badge/HA-2026.3.0+-green.svg)](https://www.home-assistant.io/)
[![GitHub License](https://img.shields.io/github/license/hass-cortex/stt-corrector)](https://github.com/hass-cortex/stt-corrector/blob/main/LICENSE)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/hass-cortex/stt-corrector)

A Home Assistant custom integration that wraps any STT (speech-to-text) entity with a three-processor correction pipeline for improved voice command accuracy.

```
Audio -----> Wrapped STT -----> Raw Text -----> Correction Pipeline -----> Final Text
             (Azure, Whisper,               |                          |
              Google, etc.)                 |  1. Language Processing  |
                                            |  2. Custom Replacements  |
                                            |  3. Similarity Matching  |
                                            +--------------------------+
```

**Example (Chinese zh-TW pipeline):** Area `客廳`, device `循環扇`, custom rule `循環3=循環扇`

| Processor | Input | Output | What happened |
|-----------|-------|--------|---------------|
| Raw STT output | | `打开客听循环3。` | Simplified, `听`(聽) instead of `厅`(廳), `3`(sān) instead of `扇`(shàn), trailing `。` |
| Language Processing | `打开客听循环3。` | `打開客聽循環3` | Stripped `。`, converted simplified to traditional (s2tw: character-level) |
| Custom Replacements | `打開客聽循環3` | `打開客聽循環扇` | Rule `循環3=循環扇` matched |
| Similarity Matching | `打開客聽循環扇` | `打開客廳循環扇` | Pinyin matched `客聽` to area name `客廳` (score 0.85) |

## Features

- **Wraps any STT entity** -- works with Azure, Whisper, Google Cloud, or any other HA STT provider without modifying it
- **Three-processor correction pipeline** -- Language Processing, Custom Replacements, and Similarity Matching, each independently toggleable
- **Chinese language support** -- script conversion (simplified/traditional via OpenCC), trailing punctuation stripping, and pinyin-based phonetic matching
- **Configurable per locale** -- each Chinese locale (zh-TW, zh-HK, zh-CN) has its own settings for script conversion, punctuation, and pinyin matching
- **Auto-collected phrase vocabulary** -- independently toggle collection from exposed entities, devices, areas, and floors
- **Language-aware matching** -- pinyin syllable comparison for Chinese, SequenceMatcher for other languages
- **Runtime statistics** -- 9 sensor entities tracking usage and correction performance ([details](docs/sensors.md))
- **Management services** -- 9 services for runtime configuration with entity targeting ([details](docs/services.md))
- **Extensible language framework** -- add support for new languages by implementing a language module
- **Fully local** -- no external API calls; all correction runs on your HA instance

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

### 4. Configure Correction (Optional)

[![Open your Home Assistant instance and show this integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=stt_corrector)

Go to the integration page and click **Configure**. The options use a menu-based layout:

```
Main Menu
  +-- Active Processors
  +-- Language Settings
  |     +-- Chinese (back to main menu)
  +-- Phrase Collection
  +-- Custom Replacements
  +-- Similarity Matching
```

| Menu Item | What you configure |
|-----------|-------------------|
| **Active Processors** | Enable or disable each processor: Language Processing, Custom Replacements, Similarity Matching. All three are enabled by default. |
| **Language Settings** | Per-locale settings for supported languages. Currently Chinese (zh-TW, zh-HK, zh-CN) with options for script conversion mode (any OpenCC direction), punctuation stripping, and pinyin matching. |
| **Phrase Collection** | Which HA sources to auto-collect phrases from (floors, areas, devices, exposed entities), plus any custom phrases you want to add. |
| **Custom Replacements** | Exact text substitution rules in `wrong=correct` format. For consistently misrecognized words. |
| **Similarity Matching** | Fuzzy matching threshold (0.5--1.0, default 0.8) and exclusion list for words that should never be corrected. |

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

**What does Language Processing do?**

Language Processing applies locale-specific text normalization before the other processors run. For Chinese locales, this includes:
- **Trailing punctuation stripping**: Removes sentence-ending punctuation (e.g., `打开灯。` becomes `打开灯`) that some STT engines append to voice commands
- **Script conversion**: Converts between simplified and traditional Chinese using any [OpenCC](https://github.com/BYVoid/OpenCC) conversion mode (e.g., `s2tw` for simplified to traditional Taiwan). Each locale can independently choose its conversion direction or disable conversion entirely.

Each setting is independently configurable per locale via the Language Settings menu.

**What is pinyin matching?**

For Chinese text, the integration converts characters to their romanized pronunciation (pinyin) and compares phonetic similarity at the syllable level. This catches cases where the STT engine recognizes a homophone instead of the intended word. Tone differences are tolerated with reduced confidence, and acoustically similar initials (e.g., l/r/n, zh/z, sh/s) receive partial credit.

**Can I use this without auto-collected phrases?**

Yes. Disable all auto-collect sources in Phrase Collection and use only custom phrases. Or disable similarity matching entirely and rely solely on custom replacements.

**What happens when I wrap an STT entity?**

A new STT entity is created (e.g., `stt.azure_speech_corrected`). The original entity is untouched and continues to work independently. You should use the **corrected** entity in your voice pipeline and automations -- it proxies audio through the original and applies corrections to the transcribed text.

**What do the similarity threshold numbers mean?**

The threshold (0.5--1.0) controls how similar a transcribed segment must be to a known phrase before it gets corrected. Practical guidance:
- **0.8 (default)** -- safe starting point. Catches clear misrecognitions without false corrections.
- **0.7--0.8** -- catches more errors, but may occasionally "correct" words that were already right.
- **Below 0.7** -- aggressive. Only use this if you have a small, distinct phrase vocabulary.

When in doubt, use `test_correction` to see candidate scores and tune from there.

**Do exclusions affect all processors?**

No. Exclusions only prevent corrections from **Similarity Matching**. Language Processing and Custom Replacements always run regardless of the exclusion list. If you need to prevent a replacement rule from firing, remove the rule itself.

**How do replacement rules handle overlapping keys?**

Replacement rules are applied in longest-key-first order. If you have rules for both `living room` and `living room light`, the longer key `living room light` matches first. This prevents shorter rules from partially matching text that a longer rule should handle.

**Do I need to configure Language Settings for non-Chinese languages?**

No. Language Settings currently only has options for Chinese. For other languages, the integration uses standard fuzzy matching (SequenceMatcher) with no special processing. Additional language modules may be added in the future.

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
| [Correction Pipeline](docs/correction-pipeline.md) | Three-processor correction pipeline with examples |
| [Sensors](docs/sensors.md) | Sensor entities for correction tracking and monitoring |
| [Services](docs/services.md) | Management services with parameters and examples |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## License

[MIT](LICENSE)

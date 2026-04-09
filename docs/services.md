# Services

All services are persistent -- changes are saved to the config entry and take effect immediately without restart.

All services require an `entity_id` parameter to target a specific STT Corrector instance.

## Limits

Services enforce input size limits to prevent configuration bloat:

| Resource | Maximum | Exception |
|----------|---------|-----------|
| Custom phrases | 500 | `phrase_list_exceeded` |
| Replacement rules | 100 | `replacement_rules_exceeded` |

These limits apply to `add_phrases`, `add_replacements`, and `set_correction_config`. The service raises a `ServiceValidationError` if the limit would be exceeded.

## Configuration Management

### `stt_corrector.add_phrases`

Add phrases to the correction known phrases list (deduplicated).

```yaml
service: stt_corrector.add_phrases
data:
  entity_id: stt.groqcloud_whisper_corrected
  phrases:
    - "Living Room Light"
    - "Kitchen Fan"
    - "Hallway Lamp"
```

### `stt_corrector.remove_phrases`

Remove phrases from the correction known phrases list.

```yaml
service: stt_corrector.remove_phrases
data:
  entity_id: stt.groqcloud_whisper_corrected
  phrases:
    - "Living Room Light"
```

### `stt_corrector.add_replacements`

Add or update custom replacement rules (wrong to correct). Replacement rules are applied in longest-key-first order to prevent partial matches from interfering with longer ones.

```yaml
service: stt_corrector.add_replacements
data:
  entity_id: stt.groqcloud_whisper_corrected
  replacements:
    "livin room": "living room"
    "kichen light": "kitchen light"
```

### `stt_corrector.remove_replacements`

Remove replacement rules by key (the "wrong" text).

```yaml
service: stt_corrector.remove_replacements
data:
  entity_id: stt.groqcloud_whisper_corrected
  keys:
    - "livin room"
```

### `stt_corrector.add_exclusions`

Add segments to the correction exclusion list. Excluded segments are never corrected by Similarity Matching. Exclusions do **not** affect Language Processing or Custom Replacements.

```yaml
service: stt_corrector.add_exclusions
data:
  entity_id: stt.groqcloud_whisper_corrected
  exclusions:
    - "pocket"
    - "chicken"
```

### `stt_corrector.remove_exclusions`

Remove segments from the correction exclusion list.

```yaml
service: stt_corrector.remove_exclusions
data:
  entity_id: stt.groqcloud_whisper_corrected
  exclusions:
    - "pocket"
```

### `stt_corrector.get_correction_config`

Returns the current correction configuration (response-only service).

```yaml
service: stt_corrector.get_correction_config
data:
  entity_id: stt.groqcloud_whisper_corrected
```

Response:
```yaml
custom_phrases: ["Living Room Light", "Kitchen Fan"]
custom_replacements:
  "livin room": "living room"
enable_language_processing: true
enable_custom_replacements: true
enable_fuzzy_matching: true
fuzzy_threshold: 0.8
custom_exclusions: ["pocket"]
auto_collect_sources: ["floors", "areas", "devices", "entities"]
language_config:
  mandarin:
    zh-tw:
      stt_language: "zh"
      opencc_mode: "traditional"
```

- `auto_collect_sources`: which HA registries to collect phrase names from. Valid values: `floors`, `areas`, `devices`, `entities`.
- `language_config`: per-language module config keyed by module name (e.g., `mandarin`), then by normalized locale (e.g., `zh-tw`). Includes `stt_language` mapping and module-specific settings. Empty object if no language settings configured.

### `stt_corrector.set_correction_config`

Import correction configuration. Accepts the same format as `get_correction_config` output. All fields are optional -- only provided fields are updated.

```yaml
service: stt_corrector.set_correction_config
data:
  entity_id: stt.groqcloud_whisper_corrected
  custom_phrases: ["Living Room Light", "Kitchen Fan"]
  custom_replacements:
    "livin room": "living room"
  enable_language_processing: true
  enable_custom_replacements: true
  enable_fuzzy_matching: true
  fuzzy_threshold: 0.8
  auto_collect_sources: ["floors", "areas", "devices", "entities"]
  language_config:
    mandarin:
      zh-tw:
        stt_language: "zh"
```

All fields are optional -- only provided fields are updated. Use `get_correction_config` to read the current state first.

## Testing & Debugging

### `stt_corrector.test_correction`

Run text through the correction pipeline with diagnostic output. Shows all candidate matches and their scores -- useful for tuning `fuzzy_threshold`.

```yaml
service: stt_corrector.test_correction
data:
  entity_id: stt.groqcloud_whisper_corrected
  text: "turn on the livin room lite"
```

Response:
```yaml
original: "turn on the livin room lite"
corrected: "turn on the living room light"
changes:
  - original_segment: "livin room lite"
    corrected_segment: "living room light"
    method: "fuzzy_match"
    confidence: 0.8823
candidates:
  - phrase: "living room light"
    segment: "livin room lite"
    score: 0.8823
    threshold: 0.8
    accepted: true
    excluded: false
  - phrase: "kitchen light"
    segment: "livin room lite"
    score: 0.5200
    threshold: 0.8
    accepted: false
    excluded: false
```

Each entry in `changes` includes:
- `original_segment` / `corrected_segment` -- the text before and after correction
- `method` -- which processor made the correction (`custom_rule`, `fuzzy_match`, `script_conversion`, or `punctuation_strip`)
- `confidence` -- similarity score (1.0 for exact matches, lower for fuzzy)

Each entry in `candidates` includes an `excluded` flag indicating whether the match was blocked by the exclusion list.

## Migration Workflow

Export from one instance, import to another:

```yaml
# 1. Export: call get_correction_config, copy the response
# 2. Import: paste into set_correction_config
service: stt_corrector.set_correction_config
data:
  # paste the full get_correction_config response here
```

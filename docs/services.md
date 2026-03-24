# Services

All services are persistent -- changes are saved to the config entry and take effect immediately without restart.

All services require an `entity_id` parameter to target a specific STT Corrector instance.

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

Add or update custom replacement rules (wrong to correct).

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

Add segments to the correction exclusion list. Excluded segments are never corrected by similarity matching.

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
enable_custom_replacements: true
enable_fuzzy_matching: true
fuzzy_threshold: 0.8
custom_exclusions: ["pocket"]
```

### `stt_corrector.set_correction_config`

Import correction configuration. Accepts the same format as `get_correction_config` output. All fields are optional -- only provided fields are updated.

```yaml
service: stt_corrector.set_correction_config
data:
  entity_id: stt.groqcloud_whisper_corrected
  custom_phrases: ["Living Room Light", "Kitchen Fan"]
  custom_replacements:
    "livin room": "living room"
  enable_custom_replacements: true
  enable_fuzzy_matching: true
  fuzzy_threshold: 0.8
```

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
  - from: "livin room lite"
    to: "living room light"
candidates:
  - phrase: "living room light"
    segment: "livin room lite"
    score: 0.8823
    threshold: 0.8
    accepted: true
  - phrase: "kitchen light"
    segment: "livin room lite"
    score: 0.5200
    threshold: 0.8
    accepted: false
```

## Migration Workflow

Export from one instance, import to another:

```yaml
# 1. Export: call get_correction_config, copy the response
# 2. Import: paste into set_correction_config
service: stt_corrector.set_correction_config
data:
  # paste the full get_correction_config response here
```

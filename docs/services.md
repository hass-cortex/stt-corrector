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
  language: "en-US"   # optional
```

Response:
```yaml
locale: "en-US"
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

`language` (optional) corrects the text as live speech in that locale would be -- pass your pipeline's language (e.g. `zh-TW`) to get the same result as speaking it. Without it, the test uses the locale of the most recent audio, which is unknown after a restart until someone speaks; then only locale-independent matching applies (e.g. no zh-TW Taiwan readings).

`locale` in the response is the locale the test ran as: the given `language`, else the most recent audio's, else `null`.

Each entry in `changes` includes:
- `original_segment` / `corrected_segment` -- the text before and after correction
- `method` -- which processor made the correction (`custom_rule`, `fuzzy_match`, `script_conversion`, or `punctuation_strip`)
- `confidence` -- similarity score (1.0 for exact matches, lower for fuzzy)

Each entry in `candidates` includes an `excluded` flag indicating whether the match was blocked by the exclusion list.

### `stt_corrector.copy_correction_config`

Copy the **full** correction configuration (replacements, phrases, processor toggles, fuzzy threshold, exclusions, auto-collect sources, language settings) from one corrector to one or more others. The targets' options are replaced wholesale; wrapped entities are never touched.

```yaml
service: stt_corrector.copy_correction_config
data:
  source_entity_id: stt.sensevoice_small_corrected
  target_entity_id:
    - stt.moonshine_tiny_chinese_corrected
    - stt.fun_asr_nano_multilingual_corrected
```

Tip: when creating a new corrector you can instead pick "Copy settings from" directly in the setup dialog.

## Learning from Mishearings

### `stt_corrector.report_mishearing`

Report that the voice pipeline produced one text while the user said another, and let the corrector learn a fix. Meant for an LLM agent that noticed the mishearing (it asked "did you mean …?" and the user agreed), an automation, or you in Developer Tools.

```yaml
service: stt_corrector.report_mishearing
data:
  heard: "今天要到樂薩"
  meant: "今天要倒垃圾"
  dry_run: false          # optional: plan and validate only
  entity_id: stt.sensevoice_small_corrected   # optional
  language: "zh-TW"       # optional
```

How the fix is chosen:

1. **Which corrector.** Each corrector keeps its last 100 recognitions (kept across restarts). The one that most recently heard `heard` -- as its corrected or raw text -- is fixed, using that recognition's raw STT text and locale. With `entity_id`, that corrector is used; if it has not heard the text, `language` is required and `heard` is taken as the raw text.
2. **What differs.** The corrector's current output is compared with `meant`. Exactly one span may differ (`到樂薩` vs `倒垃圾`); report separate mishearings one at a time. If the output already equals `meant`, nothing changes.
3. **Which fix.** Candidates are tried safest first: the meant span as a custom phrase, widened by one character of context (a longer phrase absorbs one mismatched syllable), then a replacement rule, widened by up to two characters.
4. **Only names.** A candidate must be about a known name: part of one (`立扇`) or containing one (`倒垃圾` contains `垃圾`). The corrector serves the paths that act on exact text -- local intents and sentence triggers -- and those act on names; a one-off query word (`淡江大橋`) is not learned.
5. **Validation.** A candidate is taken only if it turns the utterance into `meant` **and** leaves every recent recognition and every known phrase corrected exactly as today. Otherwise the next candidate is tried.

What happens to a fix depends on its risk:

- **A phrase is applied right away.** It only ever corrects toward a known name. It is written like `add_phrases` (same limits), shown as a persistent notification, and fired as a `stt_corrector_correction_learned` event.
- **A rule waits for your approval.** A rule rewrites its text in every sentence, and only you can tell whether `力氣 → 立扇` would break "力氣很大". It is raised as a fixable issue in **Settings → Repairs** showing the rule and the utterance, and fired as a `stt_corrector_correction_proposed` event. **Submit** re-plans and adds the rule if it still validates (or a phrase, if one now does the job); **Ignore** rejects it, and the same rule is not proposed again.

Both events carry `entity_id`, `heard`, `meant`, `type`, `wrong`, `right` -- an automation can turn them into phone notifications, with an undo action calling `remove_phrases` / `remove_replacements`.

Response:
```yaml
status: applied        # applied | proposed | fix (dry run) | already_corrected | rejected
entity_id: stt.sensevoice_small_corrected
locale: zh-TW
raw: "今天要到樂薩。"
corrected: "今天要倒垃圾"
fix:
  type: phrase         # phrase | replacement
  wrong: "到樂薩"
  right: "倒垃圾"
reason: ""             # for rejected: why each candidate failed
```

## Migration Workflow

Export from one instance, import to another:

```yaml
# Same-instance copies: prefer copy_correction_config (one call).
# Cross-instance: 1. Export via get_correction_config, copy the response
#                 2. Import: paste into set_correction_config
service: stt_corrector.set_correction_config
data:
  # paste the full get_correction_config response here
```

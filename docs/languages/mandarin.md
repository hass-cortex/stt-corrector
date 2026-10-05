# Chinese (Mandarin)

The `mandarin` language module handles the Chinese locales **zh-TW**, **zh-HK** and **zh-CN**. Code lives in `custom_components/stt_corrector/correction/languages/mandarin/`; see [How It Works](../correction-pipeline.md) for the language-independent pipeline it plugs into.

## Settings

Configured in **Language Settings > Chinese (中文)**, one section per locale.

| Setting | Locales | Default | Effect |
|---------|---------|---------|--------|
| STT Language | all | auto (prefix match) | Language sent to the wrapped STT engine -- see [STT Language Mapping](../correction-pipeline.md#stt-language-mapping) |
| Strip Trailing Punctuation | all | on | Remove sentence-ending punctuation |
| Punctuation Characters | all | `。` | Characters stripped from the end of the text |
| Script Conversion | all | zh-TW `s2tw`, zh-HK `s2hk`, zh-CN off | OpenCC conversion mode |
| Pinyin Matching | all | on | Use pinyin similarity in Similarity Matching |
| Taiwan Readings | **zh-TW only** | on | Also match words by their Taiwan pronunciation |

## Language Processing

Two processors run in order:

1. **Trailing punctuation stripping** -- Removes sentence-ending punctuation (like `。`) that STT engines sometimes append to voice commands. These characters are meaningless for home automation commands and can interfere with later matching.

2. **Script conversion** -- Converts between simplified and traditional Chinese using [OpenCC](https://github.com/BYVoid/OpenCC):

   | Mode | Direction | Description |
   |------|-----------|-------------|
   | s2tw | Simplified → Traditional | Taiwan standard |
   | s2hk | Simplified → Traditional | Hong Kong variant |
   | t2s | Traditional → Simplified | Generic conversion |
   | Off | — | Disabled |

## Similarity Matching: pinyin

The matcher converts both the input segment and each known phrase to pinyin syllables (via [pypinyin](https://github.com/mozillazg/python-pinyin)), then scores syllable by syllable:

- Exact syllable match (same base + same tone): 1.0
- Same base, different tone: 0.85 (tone differences are common STT errors)
- Similar initial consonant with same final (e.g., l/n, zh/z, sh/s): 0.70+
- Different syllable count (more than 1 apart): 0.0 (not the same phrase)

The phrase score is the average over its syllables.

## Taiwan readings (zh-TW)

pypinyin reads every word the mainland way, so a word Taiwan reads differently -- `垃圾` is `lè sè` in Taiwan, `lā jī` on the mainland -- never matches how STT spells a Taiwan speaker (`樂瑟`). For zh-TW, the matcher also scores both strings with Taiwan readings and keeps the better score, so a mainland-reading match is never lost.

The readings are in `mandarin/taiwan_readings.tsv`, generated from the [McBopomofo](https://github.com/openvanilla/McBopomofo) dictionary (MIT) -- the same source app-cortex-tts uses -- by `scripts/mandarin/taiwan_readings.py`. The table lists only words whose Taiwan reading differs from pypinyin's in an initial or final (`垃圾`, `伺服器`). Tone-only differences are left out: a same-syllable, other-tone pair already scores 0.85, so it cannot decide a match on its own.

Turn **Taiwan Readings** off when the STT engine already corrects Taiwan readings itself.

The table is defined as a difference from pypinyin, so regenerate it after a pypinyin upgrade:

```bash
uv run python scripts/mandarin/taiwan_readings.py
```

## Worked Examples

### Pinyin catches a homophone

Voice command: User says "turn on the AC". The HA device is named `冷氣`, but STT picks a homophone.

STT engine output: `打開冷器` (wrong character `器` instead of `氣`, same pronunciation)

```
Similarity Matching:
  "冷器" pinyin: ["leng3", "qi4"]
  Known phrase "冷氣" pinyin: ["leng3", "qi4"]
  Score: 1.0 (exact pinyin match) -> accepted
  Result: "打開冷氣"
```

### Taiwan reading catches a homophone (zh-TW)

Voice command: User says "take out the trash today" (`今天要倒垃圾`), pronouncing `垃圾` the Taiwan way (`lè sè`). `垃圾` is a custom phrase.

STT engine output: `今天要到樂瑟`

```
Similarity Matching:
  "樂瑟" pinyin: ["le4", "se4"]
  Known phrase "垃圾" mainland pinyin: ["la1", "ji1"] -> score 0.15
  Known phrase "垃圾" Taiwan pinyin:   ["le4", "se4"] -> score 1.0 -> accepted
  Result: "今天要到垃圾"
```

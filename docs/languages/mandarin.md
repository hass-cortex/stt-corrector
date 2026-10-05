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

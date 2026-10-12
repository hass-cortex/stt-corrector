# The Correction Library

The correction pipeline (script conversion, custom replacements, pinyin matching and the language modules) is a Python package of its own, so programs outside Home Assistant can correct their speech recognizer's text the same way the integration does. It has no Home Assistant dependency.

Its source is the integration's `correction/` directory; this repository builds it as the `stt-corrector` distribution, imported as `stt_correction`. It needs Python 3.12 or later.

## Install

```bash
# From a local checkout
uv pip install /path/to/stt-corrector

# From git (a tag, branch or commit)
uv pip install "stt-corrector @ git+https://github.com/hass-cortex/stt-corrector@<ref>"
```

## Correct a sentence

```python
from stt_correction import build_corrector

corrector = build_corrector(
    "zh-TW",                          # locale of the text, or None if unknown
    replacements={"客聽": "客廳"},     # Custom Replacements rules
    phrases=["臥室燈"],               # known phrases for Similarity Matching
)
result = corrector.correct("打开客听和卧式灯。")
result.corrected  # "打開客廳和臥室燈"
result.changes    # one CorrectionChange per change, with its method and confidence
```

`build_corrector` also takes `exclusions` (segments never corrected), `threshold` (minimum similarity, default 0.80), `language_config` (per-language settings keyed by module key, e.g. `"mandarin"`; defaults otherwise, see [Chinese (Mandarin)](languages/mandarin.md)), and `language_processing` / `similarity_matching` to switch those processors off. Custom Replacements runs when `replacements` is not empty.

A corrector is built for one locale; build a new one when the locale changes. Replace its known phrases at any time with `corrector.update_phrases([...])`. `corrector.diagnose(text)` also returns every Similarity Matching candidate with its score.

Language data (OpenCC dictionaries, the Taiwan readings table) loads on first use. To load it ahead of time, off the latency path, call `preload()` on each language module:

```python
from stt_correction import LanguageModuleRegistry

for module in LanguageModuleRegistry.all_modules():
    module.preload()
```

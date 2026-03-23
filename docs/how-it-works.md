# How It Works

STT Corrector acts as a transparent proxy between your voice pipeline and the actual STT provider:

1. **Audio arrives** from the voice pipeline
2. **Proxy buffers** the audio stream (voice commands are typically < 30 seconds)
3. **Forward** the audio to the wrapped STT entity via HA internal API
4. **Receive** the raw transcription result
5. **Stage 1 - Custom Replacements**: Apply user-defined substitution rules (sorted by key length descending to prevent partial matches)
6. **Stage 2 - Similarity Matching**: Compare text segments against known phrases using a sliding window approach. The appropriate phonetic matcher is selected based on the audio locale:
   - **Mandarin Chinese** (`zh-CN`, `zh-TW`): Pinyin-based syllable comparison with tone awareness and similar-initial boosting
   - **All other languages**: `difflib.SequenceMatcher` with word-boundary-aware windows
7. **Return** the corrected text to the voice pipeline

Known phrases for similarity matching are auto-collected from HA registries (exposed entity friendly names, device names, area names, floor names) plus any user-defined custom phrases.

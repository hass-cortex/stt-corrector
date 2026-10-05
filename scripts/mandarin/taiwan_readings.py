"""Build the Taiwan-readings table the zh-TW pinyin matcher consults.

pypinyin reads every word the mainland way, so a word Taiwan reads differently
(垃圾 lè sè, 伺服器 sì fú qì) can never phonetically match how a Taiwan speaker's
STT output spells it (樂瑟). This table lists, for each such word, its Taiwan
reading; the matcher scores a zh-TW comparison under both readings.

Sources, fetched from the McBopomofo repository (MIT), the same ones
app-cortex-tts builds its text-pipeline table from:

- ``BPMFMappings.txt`` — 140k words with their Taiwan Bopomofo readings.
- ``BPMFBase.txt`` — every character's readings, Bopomofo beside pinyin.
- ``heterophony1.list`` — which reading a character defaults to.
- ``phrase.occ`` — corpus counts, to drop dictionary artefacts.

A word goes in when a syllable of its Taiwan reading differs from pypinyin's
reading of the same (Traditional) text in its initial or final. A tone-only
difference is left out: the matcher already scores a same-syllable, other-tone
pair 0.85, so it cannot move a phrase across the threshold on its own, and it
would make up two thirds of the table. The comparison uses the project's own
pypinyin, so run it from the repository root:

    uv run python scripts/mandarin/taiwan_readings.py
"""

# pyright: reportMissingImports=false
from __future__ import annotations

import collections
import re
import sys
import urllib.request
from pathlib import Path

from pypinyin import Style, lazy_pinyin

RAW = "https://raw.githubusercontent.com/openvanilla/McBopomofo/master/Source/Data/"
FILES = ("BPMFMappings.txt", "BPMFBase.txt", "heterophony1.list", "phrase.occ")
ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).resolve().parent / ".cache" / "mcbopomofo"
OUT = (
    ROOT
    / "custom_components/stt_corrector/correction/languages/mandarin/taiwan_readings.tsv"
)

# A word the corpus never saw is as likely a dictionary artefact as a word.
MIN_WORD_OCCURRENCES = 1

_HAN = re.compile(r"^[一-鿿]+$")
# A word plus a particle (長的, 倒了) is a fragment whose reading depends on
# the sentence around it, not a word.
_FRAGMENT = re.compile(r"[的了著地得過]$")
_PINYIN = re.compile(r"^[a-z]+[1-5]?$")


def fetch(name: str) -> list[str]:
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(RAW + name) as res:  # noqa: S310 - fixed host
            path.write_bytes(res.read())
    return path.read_text(encoding="utf-8").splitlines()


def canonical(syllable: str) -> str:
    """One spelling for ü, and an explicit first tone."""
    s = syllable.replace("ü", "v").replace("lue", "lve").replace("nue", "nve")
    return s if s[-1].isdigit() else s + "1"


def runtime(syllable: str) -> str:
    """The matcher's spelling: pypinyin TONE3, neutral tone without a digit."""
    return syllable[:-1] if syllable.endswith("5") else syllable


def mainland(word: str) -> list[str]:
    return [
        canonical(s)
        for s in lazy_pinyin(word, style=Style.TONE3, neutral_tone_with_five=True)
    ]


def main() -> int:
    lines = {name: fetch(name) for name in FILES}

    bopomofo: dict[str, str] = {}
    for line in lines["BPMFBase.txt"]:
        parts = line.split()
        if len(parts) >= 3 and _PINYIN.match(parts[2]):
            bopomofo.setdefault(parts[1], canonical(parts[2]))

    def to_pinyin(zhuyin: str) -> str | None:
        if zhuyin in bopomofo:
            return bopomofo[zhuyin]
        if zhuyin.startswith("˙") and zhuyin[1:] in bopomofo:
            return bopomofo[zhuyin[1:]][:-1] + "5"
        return None

    preferred: dict[str, str] = {}
    for line in lines["heterophony1.list"]:
        parts = line.split()
        if len(parts) == 2 and (py := to_pinyin(parts[1])):
            preferred[parts[0]] = py

    occurrences: dict[str, int] = {}
    for line in lines["phrase.occ"]:
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            occurrences[parts[0]] = int(parts[1])

    words: dict[str, set[tuple[str, ...]]] = collections.defaultdict(set)
    for line in lines["BPMFMappings.txt"]:
        parts = line.split()
        if len(parts) < 2 or not _HAN.match(parts[0]) or _FRAGMENT.search(parts[0]):
            continue
        reading = tuple(to_pinyin(z) or "" for z in parts[1:])
        if "" not in reading and len(reading) == len(parts[0]):
            words[parts[0]].add(reading)

    table: dict[str, tuple[str, ...]] = {}
    skipped = collections.Counter()
    for word, readings in words.items():
        if occurrences.get(word, 0) < MIN_WORD_OCCURRENCES:
            skipped["rare"] += 1
            continue
        cn = mainland(word)
        if len(cn) != len(word):
            skipped["script"] += 1
            continue

        # Several readings: keep the one the characters default to, if that
        # picks exactly one; otherwise the choice is contextual.
        if len(readings) > 1:
            fits = [
                r
                for r in readings
                if all(preferred.get(c, s) == s for c, s in zip(word, r, strict=True))
            ]
            if len(fits) != 1:
                skipped["ambiguous"] += 1
                continue
            readings = {fits[0]}
        (tw,) = readings

        if any(a[:-1] != b[:-1] for a, b in zip(tw, cn, strict=True)):
            table[word] = tuple(runtime(s) for s in tw)

    OUT.write_text(
        "# Generated by scripts/mandarin/taiwan_readings.py from McBopomofo (MIT).\n"
        "# word\tTaiwan reading (pypinyin TONE3)\n"
        + "".join(f"{w}\t{' '.join(r)}\n" for w, r in sorted(table.items())),
        encoding="utf-8",
    )
    print(f"{len(table)} words -> {OUT}", file=sys.stderr)
    print(f"skipped: {dict(skipped)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

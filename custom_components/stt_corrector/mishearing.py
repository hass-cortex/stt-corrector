"""Turn a reported mishearing into a validated correction-config fix.

Someone downstream (a person, an LLM agent) says "STT heard X, the user
meant Y". This module decides how to make the corrector produce Y next
time, and refuses any fix that would change other text:

1. Locate the one span where the corrector's output and the meant text
   differ.
2. Try fixes safest first: add the meant span as a custom phrase, widening
   it with surrounding words (a longer phrase absorbs a mismatched
   syllable), then a replacement rule.
3. Accept the first fix that is about a known name, turns the utterance
   into the meant text and leaves every regression text exactly as the
   current config corrects it.

Only names are learned: the corrector exists for the paths that act on exact
text (local intents, sentence triggers), and those act on names. A one-off
query word (淡江大橋) is understood by an LLM agent anyway and would only
grow the phrase list.

Pure logic: callers supply a corrector factory, so this runs without Home
Assistant and in an executor thread.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

# Characters of context a candidate may add on each side of the differing
# span. A phrase widened further turns into this one utterance (打開立扇跟)
# rather than a name; a wider rule only gets more specific, so safer.
MAX_PHRASE_CONTEXT = 1
MAX_RULE_CONTEXT = 2
# Shortest phrase or replacement key worth adding
MIN_FIX_LENGTH = 2

type Correct = Callable[[str], str]
"""Run a text through a corrector and return the corrected text."""

type CorrectorFor = Callable[["Fix | None"], Correct]
"""Build a corrector for the current config plus a fix (None: unchanged)."""

type ScreenFor = Callable[["Fix"], Callable[[str], bool]]
"""Build a cheap test: could this fix change the text at all?

It must never say no for a text the fix changes; it may say yes for one
it leaves alone. A corrector holding only the fix (one phrase or one rule)
compared with one holding nothing answers it at a fraction of the cost.
"""


type FixKind = Literal["phrase", "replacement"]


@dataclass(frozen=True, slots=True)
class Fix:
    """One config change: a custom phrase, or a wrong -> right rule."""

    kind: FixKind
    wrong: str
    right: str

    def describe(self) -> str:
        if self.kind == "phrase":
            return f"phrase '{self.right}'"
        return f"rule '{self.wrong}' -> '{self.right}'"


@dataclass(frozen=True, slots=True)
class FixPlan:
    """The outcome of planning a fix for one mishearing."""

    status: Literal["fix", "already_corrected", "rejected"]
    corrected: str
    """What the utterance corrects to (with the fix, when there is one)."""
    fix: Fix | None = None
    reason: str = ""


def normalize_text(text: str) -> str:
    """Drop punctuation, symbols-as-separators and whitespace for comparison."""
    return "".join(
        ch for ch in text if unicodedata.category(ch)[0] not in ("P", "Z", "C")
    )


def changed_span(heard: str, meant: str) -> tuple[int, int, int, int] | None:
    """The single differing span (heard[a1:a2] vs meant[b1:b2]), or None.

    Adjacent differences form one span; differences with equal text between
    them are several mishearings, not one.
    """
    ops = [
        op
        for op in SequenceMatcher(None, heard, meant, autojunk=False).get_opcodes()
        if op[0] != "equal"
    ]
    if not ops:
        return None
    for prev, cur in zip(ops, ops[1:], strict=False):
        if cur[1] != prev[2]:
            return None
    return ops[0][1], ops[-1][2], ops[0][3], ops[-1][4]


def candidate_fixes(heard: str, meant: str) -> Iterator[Fix]:
    """Fixes to try, safest first: phrases (narrow to wide), then rules."""
    span = changed_span(heard, meant)
    if span is None:
        return
    a1, a2, b1, b2 = span

    def windows(context: int) -> Iterator[tuple[str, str]]:
        """(heard, meant) slices, narrowest first. Context is equal text,
        so it is the same characters on both sides."""
        for total in range(context * 2 + 1):
            for left in range(total + 1):
                right = total - left
                if (
                    left <= context
                    and right <= context
                    and a1 - left >= 0
                    and a2 + right <= len(heard)
                    and b2 + right <= len(meant)
                ):
                    yield heard[a1 - left : a2 + right], meant[b1 - left : b2 + right]

    seen: set[Fix] = set()
    passes: tuple[tuple[FixKind, int], ...] = (
        ("phrase", MAX_PHRASE_CONTEXT),
        ("replacement", MAX_RULE_CONTEXT),
    )
    for kind, context in passes:
        for wrong, right in windows(context):
            key = right if kind == "phrase" else wrong
            if len(key) < MIN_FIX_LENGTH or not right:
                continue
            fix = Fix(kind, wrong, right)
            if fix not in seen:
                seen.add(fix)
                yield fix


def is_about_a_name(text: str, names: Sequence[str]) -> bool:
    """Whether ``text`` is part of a known name, or contains one.

    Names shorter than ``MIN_FIX_LENGTH`` are ignored: a one-character name
    would make almost any text look related.
    """
    target = normalize_text(text)
    for name in names:
        name = normalize_text(name)
        if len(name) >= MIN_FIX_LENGTH and (target in name or name in target):
            return True
    return False


def plan_fix(
    raw: str,
    meant: str,
    corrector_for: CorrectorFor,
    screen_for: ScreenFor,
    regression: Sequence[str],
    names: Sequence[str],
) -> FixPlan:
    """Find the safest fix that corrects ``raw`` to ``meant``.

    Args:
        raw: What the STT engine produced for the utterance.
        meant: What the user said.
        corrector_for: Builds a corrector with a fix applied.
        screen_for: Builds the cheap could-it-change test for a fix.
        regression: Texts the fix must leave corrected exactly as today.
        names: Known names; a fix must be about one of them.

    Returns:
        The plan: a fix, ``already_corrected``, or ``rejected`` with why.
    """
    current = corrector_for(None)
    now = current(raw)
    target = normalize_text(meant)
    if normalize_text(now) == target:
        return FixPlan("already_corrected", corrected=now)

    heard = normalize_text(now)
    if changed_span(heard, target) is None:
        return FixPlan(
            "rejected",
            corrected=now,
            reason="the texts differ in several places; report one mishearing at a time",
        )

    others = [text for text in dict.fromkeys(regression) if text != raw]
    baseline: dict[str, str] = {}

    def before(text: str) -> str:
        if text not in baseline:
            baseline[text] = current(text)
        return baseline[text]

    reasons: list[str] = []
    unnamed: list[Fix] = []
    for fix in candidate_fixes(heard, target):
        if not is_about_a_name(fix.right, names):
            unnamed.append(fix)
            continue
        correct = corrector_for(fix)
        result = correct(raw)
        if normalize_text(result) != target:
            reasons.append(f"{fix.describe()} does not fix it ('{result}')")
            continue
        could_change = screen_for(fix)
        changed = [
            text
            for text in others
            if could_change(text) and correct(text) != before(text)
        ]
        if changed:
            reasons.append(
                f"{fix.describe()} would also change {len(changed)} other "
                f"text(s), e.g. '{changed[0]}'"
            )
            continue
        return FixPlan("fix", corrected=result, fix=fix)

    if unnamed and not reasons:
        # Every candidate is the same change, widened: say it once.
        return FixPlan(
            "rejected",
            corrected=now,
            reason=f"'{unnamed[0].wrong}' -> '{unnamed[0].right}' is not about a known name",
        )
    return FixPlan(
        "rejected",
        corrected=now,
        reason="; ".join(reasons) or "no fix to try",
    )

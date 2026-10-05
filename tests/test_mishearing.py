"""Tests for mishearing fix planning (mishearing.py), with real correctors."""

from custom_components.stt_corrector.mishearing import (
    Fix,
    candidate_fixes,
    changed_span,
    is_about_a_name,
    normalize_text,
    plan_fix,
)
from tests.test_pipeline_integration import _build_corrector_for_locale

PHRASES = ["入口燈", "循環扇", "立扇", "冷氣", "垃圾", "大燈", "倒垃圾無線開關"]
RULES = {"暖氣": "冷氣"}
HISTORY = ["打開入口燈", "關掉冷氣", "我到了沙發上", "倒了一杯水", "力氣很大"]
CONFIG = {"mandarin": {"zh-tw": {"script_conversion": ""}}}


def _corrector_for(fix: Fix | None):
    phrases, rules = list(PHRASES), dict(RULES)
    if fix is not None and fix.kind == "phrase":
        phrases.append(fix.right)
    elif fix is not None:
        rules[fix.wrong] = fix.right
    corrector = _build_corrector_for_locale(
        "zh-TW",
        language_config=CONFIG,
        custom_replacements=rules,
        known_phrases=phrases,
    )
    return lambda text: corrector.correct(text).corrected


def _screen_for(fix: Fix):
    # The exhaustive screen: every text could change, so validation is full.
    return lambda text: True


def _real_screen_for(fix: Fix):
    """The entity's screen: the fix alone against nothing."""

    def build(rules, phrases):
        corrector = _build_corrector_for_locale(
            "zh-TW",
            language_config=CONFIG,
            custom_replacements=rules,
            known_phrases=phrases,
        )
        return lambda text: corrector.correct(text).corrected

    bare = build(RULES, [])
    alone = (
        build(RULES, [fix.right])
        if fix.kind == "phrase"
        else build({**RULES, fix.wrong: fix.right}, [])
    )
    return lambda text: alone(text) != bare(text)


def _plan(raw: str, meant: str):
    return plan_fix(
        raw, meant, _corrector_for, _screen_for, [*HISTORY, *PHRASES], PHRASES
    )


class TestNormalizeText:
    def test_drops_punctuation_and_spaces(self) -> None:
        assert normalize_text("打開 立扇。") == "打開立扇"


class TestChangedSpan:
    def test_adjacent_differences_form_one_span(self) -> None:
        assert changed_span("今天要到樂薩", "今天要倒垃圾") == (3, 6, 3, 6)

    def test_separated_differences_are_rejected(self) -> None:
        assert changed_span("打開力戰跟大等", "打開立扇跟大燈") is None

    def test_identical_texts_have_no_span(self) -> None:
        assert changed_span("開燈", "開燈") is None


class TestCandidateFixes:
    def test_phrases_narrow_to_wide_then_rules(self) -> None:
        fixes = list(candidate_fixes("打開力戰", "打開立扇"))
        assert fixes[0] == Fix("phrase", "力戰", "立扇")
        kinds = [fix.kind for fix in fixes]
        assert kinds == sorted(kinds, key=lambda kind: kind != "phrase")
        assert Fix("replacement", "力戰", "立扇") in fixes

    def test_skips_fixes_shorter_than_two_characters(self) -> None:
        fixes = list(candidate_fixes("到", "倒"))
        assert fixes == []


class TestIsAboutAName:
    def test_part_of_a_name_or_containing_one(self) -> None:
        assert is_about_a_name("立扇", PHRASES)
        assert is_about_a_name("倒垃圾", PHRASES)

    def test_a_one_off_query_word_is_not(self) -> None:
        assert not is_about_a_name("淡江大橋", PHRASES)

    def test_one_character_names_do_not_count(self) -> None:
        assert not is_about_a_name("開燈", ["燈"])


class TestPlanFix:
    def test_a_one_off_query_word_is_not_learned(self) -> None:
        plan = _plan("找一張贛江大橋的圖", "找一張淡江大橋的圖")
        assert plan.status == "rejected"
        assert "not about a known name" in plan.reason

    def test_near_sound_learns_the_wider_phrase(self) -> None:
        """樂薩 misses 垃圾 by a syllable; 倒垃圾 absorbs it."""
        plan = _plan("今天要到樂薩", "今天要倒垃圾")
        assert plan.status == "fix"
        assert plan.fix == Fix("phrase", "到樂薩", "倒垃圾")
        assert plan.corrected == "今天要倒垃圾"

    def test_falls_back_to_a_rule_when_no_phrase_fixes_it(self) -> None:
        """zh/sh scores 0, so only a rule turns 力戰 into 立扇."""
        plan = _plan("打開力戰。", "打開立扇")
        assert plan.status == "fix"
        assert plan.fix == Fix("replacement", "力戰", "立扇")

    def test_rejects_a_fix_that_changes_other_text(self) -> None:
        """力氣→立扇 would rewrite 力氣很大; the narrower 開力氣 is taken."""
        plan = _plan("開力氣", "開立扇")
        assert plan.fix == Fix("replacement", "開力氣", "開立扇")

    def test_differences_the_corrector_already_fixes_are_ignored(self) -> None:
        """大等→大燈 is fixed today, leaving 力戰 as the one mishearing."""
        plan = _plan("打開力戰跟大等", "打開立扇跟大燈")
        assert plan.fix == Fix("replacement", "力戰", "立扇")

    def test_already_corrected(self) -> None:
        plan = _plan("關閉冷器", "關閉冷氣")
        assert plan.status == "already_corrected"
        assert plan.fix is None

    def test_several_differences_are_rejected(self) -> None:
        plan = _plan("力戰和力戰", "立扇和立扇")
        assert plan.status == "rejected"
        assert "one mishearing at a time" in plan.reason

    def test_rejection_explains_each_attempt(self) -> None:
        plan = plan_fix(
            "開力氣",
            "開立扇",
            _corrector_for,
            _screen_for,
            [*HISTORY, *PHRASES, "開力氣很大", "開立扇"],
            PHRASES,
        )
        assert plan.status == "rejected"
        assert "would also change" in plan.reason

    def test_screen_still_catches_the_text_a_fix_would_change(self) -> None:
        exhaustive = _plan("開力氣", "開立扇")
        screened = plan_fix(
            "開力氣",
            "開立扇",
            _corrector_for,
            _real_screen_for,
            [*HISTORY, *PHRASES],
            PHRASES,
        )
        assert screened == exhaustive

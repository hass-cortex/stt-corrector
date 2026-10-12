"""Tests for build_corrector: a corrector from given rules and phrases."""

from custom_components.stt_corrector.correction import build_corrector


class TestBuildCorrector:
    """A consumer outside Home Assistant builds a corrector from plain values."""

    def test_corrects_with_rules_and_phrases(self) -> None:
        sc = build_corrector("zh-TW", replacements={"客聽": "客廳"}, phrases=["臥室燈"])

        # Script conversion, then the rule, then pinyin matching against the phrase.
        result = sc.correct("打开客听和卧式灯。")

        assert result.corrected == "打開客廳和臥室燈"

    def test_unknown_locale_still_applies_rules_and_phrases(self) -> None:
        sc = build_corrector(None, replacements={"開等": "開燈"}, phrases=["臥室燈"])

        assert sc.correct("開等臥室登").corrected == "開燈臥室燈"

    def test_switched_off_processors_leave_text_alone(self) -> None:
        sc = build_corrector(
            "zh-TW",
            phrases=["臥室燈"],
            language_processing=False,
            similarity_matching=False,
        )

        assert sc.correct("打开卧式灯。").corrected == "打开卧式灯。"

    def test_phrases_can_change_after_building(self) -> None:
        sc = build_corrector("zh-TW")
        sc.update_phrases(["臥室燈"])

        assert sc.correct("卧式灯").corrected == "臥室燈"

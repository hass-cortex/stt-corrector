"""Tests for Taiwan readings (languages/mandarin/taiwan_readings)."""

from custom_components.stt_corrector.correction.languages.mandarin import (
    TaiwanReadings,
    get_taiwan_readings,
    pinyin_similarity,
)


class TestTaiwanReadings:
    """Tests for TaiwanReadings and its use in pinyin_similarity."""

    readings = TaiwanReadings(
        {"垃圾": ("le4", "se4"), "垃圾桶": ("le4", "se4", "tong3")}
    )

    def test_listed_word_takes_taiwan_reading(self) -> None:
        assert self.readings.pinyin("倒垃圾提醒") == [
            "dao4",
            "le4",
            "se4",
            "ti2",
            "xing3",
        ]

    def test_longest_listed_word_wins(self) -> None:
        assert self.readings.pinyin("垃圾桶") == ["le4", "se4", "tong3"]

    def test_text_without_listed_word_returns_none(self) -> None:
        assert self.readings.pinyin("開燈") is None

    def test_taiwan_homophone_matches(self) -> None:
        """樂瑟 is how STT spells a Taiwan speaker's 垃圾 (lè sè)."""
        assert pinyin_similarity("樂瑟", "垃圾") < 0.5
        assert pinyin_similarity("樂瑟", "垃圾", self.readings) == 1.0

    def test_mainland_homophone_still_matches(self) -> None:
        """Taiwan readings add a match; they never take one away."""
        assert pinyin_similarity("拉雞", "垃圾", self.readings) == 1.0

    def test_repr_names_the_readings(self) -> None:
        from custom_components.stt_corrector.correction.languages.mandarin import (
            PinyinMatcher,
        )

        assert repr(PinyinMatcher(self.readings)) == "PinyinMatcher(taiwan_readings)"
        assert repr(PinyinMatcher()) == "PinyinMatcher()"

    def test_shipped_table_loads(self) -> None:
        shipped = get_taiwan_readings()
        assert shipped.pinyin("垃圾") == ["le4", "se4"]
        assert shipped.pinyin("伺服器") == ["si4", "fu2", "qi4"]
        # Tone-only differences are left out of the table
        assert shipped.pinyin("星期") is None

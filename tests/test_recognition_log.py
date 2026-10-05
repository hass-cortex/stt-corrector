"""Tests for RecognitionLog (recognition_log.py)."""

from unittest.mock import MagicMock

import pytest

from custom_components.stt_corrector.recognition_log import (
    MAX_RECOGNITIONS,
    RecognitionLog,
)


def _log(entry_id: str = "entry") -> RecognitionLog:
    return RecognitionLog(MagicMock(), entry_id)


class TestRecognitionLog:
    def test_finds_by_corrected_or_raw_text_ignoring_punctuation(self) -> None:
        log = _log()
        log.add("今天要到樂瑟。", "今天要到垃圾", "zh-TW")
        assert log.find("今天要到垃圾").raw == "今天要到樂瑟。"
        assert log.find("今天要到樂瑟").corrected == "今天要到垃圾"
        assert log.find("開燈") is None

    def test_newest_match_wins(self) -> None:
        log = _log()
        log.add("開燈", "開燈", "zh-CN")
        log.add("開燈", "開燈", "zh-TW")
        assert log.find("開燈").locale == "zh-TW"

    def test_raw_texts_by_locale_deduplicated(self) -> None:
        log = _log()
        log.add("開燈", "開燈", "zh-TW")
        log.add("開燈", "開燈", "zh-TW")
        log.add("lights on", "lights on", "en-US")
        assert log.raw_texts("zh-TW") == ["開燈"]

    def test_keeps_only_the_newest(self) -> None:
        log = _log()
        for i in range(MAX_RECOGNITIONS + 5):
            log.add(f"text {i}", f"text {i}", "en-US")
        texts = log.raw_texts("en-US")
        assert len(texts) == MAX_RECOGNITIONS
        assert texts[0] == "text 5"

    @pytest.mark.asyncio
    async def test_survives_a_restart_until_the_entry_is_removed(self) -> None:
        log = _log("persisted")
        log.add("開燈", "開燈", "zh-TW")

        restored = _log("persisted")
        await restored.async_load()
        assert restored.find("開燈") is not None

        await RecognitionLog.async_remove(MagicMock(), "persisted")
        emptied = _log("persisted")
        await emptied.async_load()
        assert emptied.find("開燈") is None

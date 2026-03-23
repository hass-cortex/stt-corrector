"""Tests for STT Corrector runtime data models."""

from __future__ import annotations

from custom_components.stt_corrector.models import (
    CorrectionStats,
    STTCorrectorRuntimeData,
)


class TestSTTCorrectorRuntimeData:
    def test_defaults(self):
        data = STTCorrectorRuntimeData()
        assert data.entity is None
        assert data.sensors == []

    def test_sensors_list_is_independent(self):
        """Each instance gets its own sensors list."""
        a = STTCorrectorRuntimeData()
        b = STTCorrectorRuntimeData()
        a.sensors.append("x")
        assert b.sensors == []


class TestCorrectionStats:
    def test_required_field(self):
        stats = CorrectionStats(result_state="success")
        assert stats.result_state == "success"
        assert stats.correction_applied is False
        assert stats.language == ""
        assert stats.raw_text is None
        assert stats.corrected_text is None

    def test_all_fields(self):
        stats = CorrectionStats(
            result_state="success",
            correction_applied=True,
            language="zh-TW",
            raw_text="原始",
            corrected_text="修正",
        )
        assert stats.correction_applied is True
        assert stats.language == "zh-TW"
        assert stats.raw_text == "原始"
        assert stats.corrected_text == "修正"

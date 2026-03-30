"""Tests for CorrectionConfig."""

from __future__ import annotations

from custom_components.stt_corrector.correction_config import CorrectionConfig


class TestCorrectionConfigDefaults:
    """Verify default values match expected constants."""

    def test_defaults(self):
        cfg = CorrectionConfig()
        assert cfg.enable_language_processing is True
        assert cfg.enable_custom_replacements is True
        assert cfg.enable_fuzzy_matching is True
        assert cfg.fuzzy_threshold == 0.80
        assert cfg.custom_phrases == []
        assert cfg.custom_replacements == {}
        assert cfg.custom_exclusions == []
        assert cfg.auto_collect_sources == [
            "floors",
            "areas",
            "devices",
            "entities",
        ]
        assert cfg.language_config == {}

    def test_no_enable_entity_hints_field(self):
        """CorrectionConfig must NOT have enable_entity_hints (Azure-specific)."""
        cfg = CorrectionConfig()
        assert not hasattr(cfg, "enable_entity_hints")


class TestCorrectionConfigFromOptions:
    """Verify from_options factory method."""

    def test_from_empty_options(self):
        cfg = CorrectionConfig.from_options({})
        assert cfg == CorrectionConfig()

    def test_from_full_options(self):
        options = {
            "active_processors": ["language_processing"],
            "fuzzy_threshold": 0.90,
            "custom_phrases": ["hello", "world"],
            "custom_replacements": {"hi": "hello"},
            "custom_exclusions": ["ignore_this"],
            "auto_collect_sources": ["areas"],
        }
        cfg = CorrectionConfig.from_options(options)
        assert cfg.enable_language_processing is True
        assert cfg.enable_custom_replacements is False
        assert cfg.enable_fuzzy_matching is False
        assert cfg.fuzzy_threshold == 0.90
        assert cfg.custom_phrases == ["hello", "world"]
        assert cfg.custom_replacements == {"hi": "hello"}
        assert cfg.custom_exclusions == ["ignore_this"]
        assert cfg.auto_collect_sources == ["areas"]

    def test_from_partial_options(self):
        options = {"fuzzy_threshold": 0.65}
        cfg = CorrectionConfig.from_options(options)
        assert cfg.fuzzy_threshold == 0.65
        # All other fields should be defaults
        assert cfg.enable_custom_replacements is True
        assert cfg.enable_fuzzy_matching is True


class TestCorrectionConfigLanguageProcessing:
    """Tests for language processing config fields."""

    def test_default_enable_language_processing(self):
        cfg = CorrectionConfig()
        assert cfg.enable_language_processing is True

    def test_default_language_config_empty(self):
        cfg = CorrectionConfig()
        assert cfg.language_config == {}

    def test_from_options_with_language_config(self):
        options = {
            "active_processors": [
                "language_processing",
                "replacements",
                "similarity",
            ],
            "language_config": {
                "mandarin": {
                    "zh-tw": {"script_conversion": True, "pinyin_matching": True}
                }
            },
        }
        cfg = CorrectionConfig.from_options(options)
        assert cfg.enable_language_processing is True
        assert "mandarin" in cfg.language_config
        assert cfg.language_config["mandarin"]["zh-tw"]["script_conversion"] is True

    def test_from_options_missing_language_config_defaults(self):
        cfg = CorrectionConfig.from_options({})
        assert cfg.enable_language_processing is True
        assert cfg.language_config == {}

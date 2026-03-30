"""Tests for LanguageModule ABC, MandarinModule, and LanguageModuleRegistry."""

from custom_components.stt_corrector.correction.languages.mandarin import (
    ChineseScriptConverter,
    MandarinModule,
    PinyinMatcher,
)
from custom_components.stt_corrector.correction.languages.registry import (
    LanguageModuleRegistry,
)
from custom_components.stt_corrector.correction.matchers import DefaultMatcher
from custom_components.stt_corrector.correction.processors.punctuation import (
    TrailingPunctuationStripper,
)


class TestMandarinModuleMetadata:
    """Tests for MandarinModule metadata methods."""

    def test_locales(self) -> None:
        module = MandarinModule()
        assert module.locales() == ("zh-TW", "zh-HK", "zh-CN")

    def test_module_key(self) -> None:
        module = MandarinModule()
        assert module.module_key() == "mandarin"

    def test_menu_label(self) -> None:
        module = MandarinModule()
        assert module.menu_label() == "Chinese (中文)"


class TestMandarinModuleDefaultConfig:
    """Tests for MandarinModule default configuration."""

    def test_default_config_keys(self) -> None:
        module = MandarinModule()
        cfg = module.default_config()
        assert set(cfg.keys()) == {"zh-tw", "zh-hk", "zh-cn"}

    def test_zh_tw_defaults(self) -> None:
        module = MandarinModule()
        cfg = module.default_config()
        assert cfg["zh-tw"]["strip_trailing_punctuation"] is True
        assert cfg["zh-tw"]["trailing_punctuation"] == "。"
        assert cfg["zh-tw"]["script_conversion"] is True
        assert cfg["zh-tw"]["pinyin_matching"] is True

    def test_zh_hk_defaults(self) -> None:
        module = MandarinModule()
        cfg = module.default_config()
        assert cfg["zh-hk"]["strip_trailing_punctuation"] is True
        assert cfg["zh-hk"]["trailing_punctuation"] == "。"
        assert cfg["zh-hk"]["script_conversion"] is True
        assert cfg["zh-hk"]["pinyin_matching"] is True

    def test_zh_cn_defaults(self) -> None:
        module = MandarinModule()
        cfg = module.default_config()
        assert cfg["zh-cn"]["strip_trailing_punctuation"] is True
        assert cfg["zh-cn"]["trailing_punctuation"] == "。"
        assert cfg["zh-cn"]["script_conversion"] is False
        assert cfg["zh-cn"]["pinyin_matching"] is True


class TestMandarinModuleGetProcessors:
    """Tests for MandarinModule.get_processors."""

    def test_default_config_returns_stripper_and_converter(self) -> None:
        """With defaults, zh-TW should have stripper + converter."""
        module = MandarinModule()
        config = module.default_config()
        processors = module.get_processors("zh-TW", config)
        assert len(processors) == 2
        assert isinstance(processors[0], TrailingPunctuationStripper)
        assert isinstance(processors[1], ChineseScriptConverter)

    def test_only_script_conversion(self) -> None:
        module = MandarinModule()
        config = {
            "zh-tw": {"strip_trailing_punctuation": False, "script_conversion": True}
        }
        processors = module.get_processors("zh-TW", config)
        assert len(processors) == 1
        assert isinstance(processors[0], ChineseScriptConverter)

    def test_only_punctuation_strip(self) -> None:
        module = MandarinModule()
        config = {
            "zh-tw": {
                "strip_trailing_punctuation": True,
                "trailing_punctuation": "。",
                "script_conversion": False,
            }
        }
        processors = module.get_processors("zh-TW", config)
        assert len(processors) == 1
        assert isinstance(processors[0], TrailingPunctuationStripper)

    def test_both_disabled_returns_empty(self) -> None:
        module = MandarinModule()
        config = {
            "zh-tw": {"strip_trailing_punctuation": False, "script_conversion": False}
        }
        processors = module.get_processors("zh-TW", config)
        assert processors == []

    def test_missing_locale_config_defaults_to_strip_enabled(self) -> None:
        """When locale config is missing, strip defaults to True."""
        module = MandarinModule()
        processors = module.get_processors("zh-TW", {})
        assert len(processors) == 1
        assert isinstance(processors[0], TrailingPunctuationStripper)

    def test_zh_cn_default_has_stripper_no_converter(self) -> None:
        """zh-CN defaults: strip enabled, script_conversion disabled."""
        module = MandarinModule()
        config = module.default_config()
        processors = module.get_processors("zh-CN", config)
        assert len(processors) == 1
        assert isinstance(processors[0], TrailingPunctuationStripper)

    def test_custom_punctuation_chars(self) -> None:
        module = MandarinModule()
        config = {
            "zh-tw": {
                "strip_trailing_punctuation": True,
                "trailing_punctuation": "。？！",
            }
        }
        processors = module.get_processors("zh-TW", config)
        assert len(processors) == 1
        result, _ = processors[0].process("你好？")
        assert result == "你好"

    def test_underscore_locale_format(self) -> None:
        """Locale with underscore separator (zh_TW) should work."""
        module = MandarinModule()
        config = module.default_config()
        processors = module.get_processors("zh_TW", config)
        assert len(processors) == 2
        assert isinstance(processors[0], TrailingPunctuationStripper)
        assert isinstance(processors[1], ChineseScriptConverter)

    def test_stripper_runs_before_converter(self) -> None:
        """Punctuation is stripped before script conversion."""
        module = MandarinModule()
        config = module.default_config()
        processors = module.get_processors("zh-TW", config)
        # Apply in order: strip then convert
        text = "开灯。"
        for p in processors:
            text, _ = p.process(text)
        assert text == "開燈"


class TestMandarinModuleGetMatcher:
    """Tests for MandarinModule.get_matcher."""

    def test_pinyin_enabled_returns_matcher(self) -> None:
        module = MandarinModule()
        config = {"zh-tw": {"pinyin_matching": True}}
        matcher = module.get_matcher("zh-TW", config)
        assert isinstance(matcher, PinyinMatcher)

    def test_pinyin_disabled_returns_none(self) -> None:
        module = MandarinModule()
        config = {"zh-tw": {"pinyin_matching": False}}
        matcher = module.get_matcher("zh-TW", config)
        assert matcher is None

    def test_missing_locale_config_defaults_to_matcher(self) -> None:
        """When locale config is missing, pinyin_matching defaults to True."""
        module = MandarinModule()
        matcher = module.get_matcher("zh-TW", {})
        assert isinstance(matcher, PinyinMatcher)


class TestLanguageModuleRegistry:
    """Tests for LanguageModuleRegistry."""

    def test_get_module_for_zh_tw(self) -> None:
        module = LanguageModuleRegistry.get_module_for_locale("zh-TW")
        assert module is not None
        assert module.module_key() == "mandarin"

    def test_get_module_for_zh_cn(self) -> None:
        module = LanguageModuleRegistry.get_module_for_locale("zh-CN")
        assert module is not None
        assert module.module_key() == "mandarin"

    def test_get_module_for_zh_hk(self) -> None:
        module = LanguageModuleRegistry.get_module_for_locale("zh-HK")
        assert module is not None
        assert module.module_key() == "mandarin"

    def test_get_module_for_lowercase_locale(self) -> None:
        """HA Voice Pipeline sends lowercase locales."""
        module = LanguageModuleRegistry.get_module_for_locale("zh-tw")
        assert module is not None
        assert module.module_key() == "mandarin"

    def test_get_module_for_underscore_locale(self) -> None:
        """Locale with underscore separator (zh_TW) should match."""
        module = LanguageModuleRegistry.get_module_for_locale("zh_TW")
        assert module is not None
        assert module.module_key() == "mandarin"

    def test_get_module_for_underscore_lowercase(self) -> None:
        """Locale zh_tw (underscore, lowercase) should match."""
        module = LanguageModuleRegistry.get_module_for_locale("zh_tw")
        assert module is not None
        assert module.module_key() == "mandarin"

    def test_get_module_for_english_returns_none(self) -> None:
        module = LanguageModuleRegistry.get_module_for_locale("en-US")
        assert module is None

    def test_get_module_for_japanese_returns_none(self) -> None:
        module = LanguageModuleRegistry.get_module_for_locale("ja-JP")
        assert module is None

    def test_all_modules_includes_mandarin(self) -> None:
        modules = LanguageModuleRegistry.all_modules()
        keys = [m.module_key() for m in modules]
        assert "mandarin" in keys

    def test_get_module_by_key(self) -> None:
        module = LanguageModuleRegistry.get_module_by_key("mandarin")
        assert module is not None
        assert module.module_key() == "mandarin"

    def test_get_module_by_key_unknown_returns_none(self) -> None:
        module = LanguageModuleRegistry.get_module_by_key("unknown")
        assert module is None


class TestLanguageModuleRegistryGetMatchers:
    """Tests for LanguageModuleRegistry.get_matchers (merged from MatcherRegistry)."""

    def test_zh_cn_includes_pinyin(self) -> None:
        matchers = LanguageModuleRegistry.get_matchers("zh-CN")
        assert len(matchers) == 2
        assert isinstance(matchers[0], PinyinMatcher)
        assert isinstance(matchers[1], DefaultMatcher)

    def test_english_uses_default_only(self) -> None:
        matchers = LanguageModuleRegistry.get_matchers("en-US")
        assert len(matchers) == 1
        assert isinstance(matchers[0], DefaultMatcher)

    def test_none_locale_includes_all(self) -> None:
        matchers = LanguageModuleRegistry.get_matchers(None)
        assert len(matchers) == 2
        assert isinstance(matchers[0], PinyinMatcher)
        assert isinstance(matchers[1], DefaultMatcher)

    def test_default_matcher_always_last(self) -> None:
        for locale in ["zh-CN", "en-US", None]:
            matchers = LanguageModuleRegistry.get_matchers(locale)
            assert isinstance(matchers[-1], DefaultMatcher)

    def test_underscore_locale(self) -> None:
        matchers = LanguageModuleRegistry.get_matchers("zh_tw")
        assert len(matchers) == 2
        assert isinstance(matchers[0], PinyinMatcher)

    def test_pinyin_disabled_via_config(self) -> None:
        config = {"mandarin": {"zh-tw": {"pinyin_matching": False}}}
        matchers = LanguageModuleRegistry.get_matchers("zh-TW", language_config=config)
        assert len(matchers) == 1
        assert isinstance(matchers[0], DefaultMatcher)

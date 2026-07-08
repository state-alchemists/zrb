"""Tests for theme-preset resolution (config/theme.py + ZRB_THEME wiring)."""

import logging

import pytest

from zrb.config.config import Config
from zrb.config.theme import (
    DEFAULT_THEME,
    THEMES,
    get_theme,
    register_theme,
    theme_value,
)


class TestThemeRegistry:
    def test_builtin_themes_present(self):
        assert "dark" in THEMES
        assert "light" in THEMES
        assert DEFAULT_THEME == "dark"

    def test_get_theme_known(self):
        assert get_theme("light") is THEMES["light"]

    def test_get_theme_unknown_falls_back_to_default(self, caplog):
        with caplog.at_level(logging.WARNING):
            resolved = get_theme("does-not-exist")
        assert resolved is THEMES[DEFAULT_THEME]
        assert "Unknown theme" in caplog.text

    def test_theme_value_absent_key_returns_empty(self):
        assert theme_value("dark", "NO_SUCH_KEY") == ""

    def test_unknown_theme_does_not_recurse_through_log_formatter(self, monkeypatch):
        # Regression: the root logger's formatter styles records via themed
        # CLI_COLOR_* knobs, so resolving an unknown theme (which logs a
        # warning) re-enters get_theme during formatting. The once-per-name
        # guard must break that cycle instead of blowing the stack.
        from zrb.util.cli.style import stylize_muted

        monkeypatch.setenv("ZRB_THEME", "recursion-regression-theme")

        class _ThemedFormatter(logging.Formatter):
            def format(self, record):
                return stylize_muted(super().format(record))

        handler = logging.StreamHandler()
        handler.setFormatter(_ThemedFormatter())
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            # Must not raise RecursionError while the themed formatter is live.
            assert get_theme("recursion-regression-theme") is THEMES[DEFAULT_THEME]
        finally:
            root.removeHandler(handler)

    def test_register_theme_is_used(self, monkeypatch):
        monkeypatch.setitem(THEMES, "unit-test-theme", {"LLM_UI_STYLE_TEXT": "#abcdef"})
        assert theme_value("unit-test-theme", "LLM_UI_STYLE_TEXT") == "#abcdef"

    def test_register_theme_merges_onto_dark(self, monkeypatch):
        # A partial registered theme must inherit unspecified knobs from `dark`
        # instead of blanking them to "".
        monkeypatch.delitem(THEMES, "unit-partial-theme", raising=False)
        register_theme("unit-partial-theme", {"CLI_COLOR_WARNING": "orange"})
        try:
            assert theme_value("unit-partial-theme", "CLI_COLOR_WARNING") == "orange"
            # Unspecified knob falls back to the dark value, not "".
            assert theme_value(
                "unit-partial-theme", "LLM_UI_STYLE_TEXT"
            ) == theme_value("dark", "LLM_UI_STYLE_TEXT")
            assert theme_value("unit-partial-theme", "LLM_UI_STYLE_TEXT") != ""
        finally:
            THEMES.pop("unit-partial-theme", None)

    def test_register_theme_helper_copies_input(self, monkeypatch):
        # Ensure register_theme stores an independent copy (mutating the source
        # dict afterwards must not leak into the registered theme).
        monkeypatch.setitem(THEMES, "unit-copy-theme", {})
        source = {"CLI_COLOR_INFO": "green"}
        register_theme("unit-copy-theme", source)
        source["CLI_COLOR_INFO"] = "red"
        assert theme_value("unit-copy-theme", "CLI_COLOR_INFO") == "green"


class TestThemeResolution:
    def test_default_theme_is_dark(self, monkeypatch):
        monkeypatch.delenv("ZRB_THEME", raising=False)
        assert Config().THEME == "dark"

    def test_dark_defaults_match_historical_values(self, monkeypatch):
        monkeypatch.delenv("ZRB_THEME", raising=False)
        for key in ("ZRB_LLM_UI_STYLE_TITLE_BAR", "ZRB_CLI_COLOR_INFO"):
            monkeypatch.delenv(key, raising=False)
        cfg = Config()
        assert cfg.LLM_UI_STYLE_TITLE_BAR == "#ffffff"
        assert cfg.LLM_UI_STYLE_MARKDOWN_H1 == "bold magenta"
        assert cfg.CLI_COLOR_INFO == "cyan"
        assert cfg.CLI_STYLE_MUTED == "faint"

    def test_theme_switch_changes_defaults(self, monkeypatch):
        monkeypatch.setenv("ZRB_THEME", "light")
        monkeypatch.delenv("ZRB_LLM_UI_STYLE_TEXT", raising=False)
        monkeypatch.delenv("ZRB_CLI_COLOR_INFO", raising=False)
        cfg = Config()
        assert cfg.LLM_UI_STYLE_TEXT == "#1a1a1a"
        assert cfg.CLI_COLOR_INFO == "blue"

    def test_explicit_env_overrides_theme(self, monkeypatch):
        monkeypatch.setenv("ZRB_THEME", "light")
        monkeypatch.setenv("ZRB_LLM_UI_STYLE_TEXT", "#123456")
        assert Config().LLM_UI_STYLE_TEXT == "#123456"

    def test_unknown_theme_resolves_dark_defaults(self, monkeypatch):
        monkeypatch.setenv("ZRB_THEME", "bogus")
        monkeypatch.delenv("ZRB_LLM_UI_STYLE_TEXT", raising=False)
        assert Config().LLM_UI_STYLE_TEXT == "#eeeeee"

    def test_newly_exposed_knobs_have_dark_defaults(self, monkeypatch):
        monkeypatch.delenv("ZRB_THEME", raising=False)
        for key in (
            "ZRB_LLM_UI_STYLE_TITLE_BAR_BG",
            "ZRB_LLM_UI_STYLE_PROMPT",
            "ZRB_LLM_UI_STYLE_MARKDOWN_LINK",
        ):
            monkeypatch.delenv(key, raising=False)
        cfg = Config()
        assert cfg.LLM_UI_STYLE_TITLE_BAR_BG == "ansipurple"
        assert cfg.LLM_UI_STYLE_PROMPT == "ansibrightblue"
        assert cfg.LLM_UI_STYLE_MARKDOWN_LINK == "bold bright_cyan underline"

    @pytest.mark.parametrize("theme", ["dark", "light"])
    def test_registered_themes_cover_all_wired_knobs(self, theme, monkeypatch):
        # Every knob wired to the theme must have a value in both built-in
        # themes, otherwise switching themes would silently blank a style.
        monkeypatch.setenv("ZRB_THEME", theme)
        for key in THEMES["dark"]:
            assert key in THEMES[theme], f"{key} missing from {theme} theme"

"""Named style-theme presets for the CLI and LLM UI.

A *theme* is a named bundle of default style values. The ``ZRB_THEME`` knob
(``CFG.THEME``) selects one; every themed style knob resolves its **default**
from the active theme via :func:`theme_default` (wired as each field's
``EnvField(default_factory=...)``). An explicitly set ``ZRB_*`` style env still
wins, because ``EnvField`` reads the env first and only calls the factory when
the knob is unset. See ADR-0084.

This module is pure data plus helpers — it must **not** import config, to keep
``zrb.config`` importable without a cycle. Keys are style-knob names (e.g.
``LLM_UI_STYLE_TITLE_BAR``); values are whatever string that knob's consumer
expects (prompt_toolkit style strings, Rich color names, or hex).

Themes are user/plugin-extensible via :func:`register_theme`, mirroring
``register_model_profile`` (``llm/prompt/profile.py``). Registered themes are
merged onto the ``dark`` palette, so a partial theme only lists what it changes.
See :func:`register_theme` for the ``zrb_init.py`` recipe, and
``examples/themes/`` for a full worked example (monokai).
"""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

DEFAULT_THEME = "dark"

_WARNED_UNKNOWN: set[str] = set()

# "dark" reproduces the historical hardcoded defaults exactly, so a default
# install is visually unchanged. "light" is a dark-on-light variant that avoids
# pale-on-white foregrounds (no bright yellow, near-white text, etc.).
_DARK: dict[str, str] = {
    # LLM UI (prompt_toolkit style strings)
    "LLM_UI_STYLE_TITLE_BAR": "#ffffff",
    "LLM_UI_STYLE_TITLE_BAR_BG": "ansipurple",
    "LLM_UI_STYLE_INFO_BAR": "#ffffff",
    "LLM_UI_STYLE_FRAME": "#888888",
    "LLM_UI_STYLE_FRAME_LABEL": "#ffff00",
    "LLM_UI_STYLE_INPUT_FRAME": "#888888",
    "LLM_UI_STYLE_PROMPT": "ansibrightblue",
    "LLM_UI_STYLE_THINKING": "ansigreen",
    "LLM_UI_STYLE_CONFIRMATION": "ansiyellow",
    "LLM_UI_STYLE_FAINT": "#888888",
    "LLM_UI_STYLE_OUTPUT_FIELD": "#eeeeee",
    "LLM_UI_STYLE_INPUT_FIELD": "#eeeeee",
    "LLM_UI_STYLE_TEXT": "#eeeeee",
    "LLM_UI_STYLE_STATUS": "ansiwhite",
    "LLM_UI_STYLE_BOTTOM_TOOLBAR": "noinherit",
    "LLM_UI_STYLE_CHOICE_BG": "#1f1f1f",
    "LLM_UI_STYLE_CHOICE_SELECTED_BG": "#264f78",
    "LLM_UI_STYLE_MODE_NORMAL": "fg:ansigreen",
    "LLM_UI_STYLE_MODE_ACCEPT_EDITS": "fg:ansiyellow bold",
    "LLM_UI_STYLE_MODE_PLAN": "fg:ansiblue bold",
    "LLM_UI_STYLE_MODE_YOLO": "fg:ansired bold",
    "LLM_UI_STYLE_MODE_CUSTOM": "fg:ansiyellow bold",
    "LLM_UI_STYLE_INFO_YOLO_ON": "ansired",
    "LLM_UI_STYLE_INFO_YOLO_PARTIAL": "ansiyellow",
    "LLM_UI_STYLE_INFO_YOLO_OFF": "ansigreen",
    "LLM_UI_STYLE_INFO_PLAN_ON": "ansiblue",
    "LLM_UI_STYLE_INFO_PLAN_OFF": "ansigreen",
    # Markdown rendering (Rich style strings)
    "LLM_UI_STYLE_MARKDOWN_LINK": "bold bright_cyan underline",
    "LLM_UI_STYLE_MARKDOWN_LINK_URL": "italic bright_cyan underline",
    "LLM_UI_STYLE_MARKDOWN_H1": "bold magenta",
    "LLM_UI_STYLE_MARKDOWN_CODE": "bold white",
    # CLI semantic colors/styles (Rich color names)
    "CLI_COLOR_WARNING": "yellow",
    "CLI_STYLE_WARNING": "bold",
    "CLI_COLOR_ERROR": "red",
    "CLI_STYLE_ERROR": "bold",
    "CLI_COLOR_SUCCESS": "green",
    "CLI_STYLE_SUCCESS": "",
    "CLI_COLOR_HIGHLIGHT": "yellow",
    "CLI_STYLE_HIGHLIGHT": "bold",
    "CLI_COLOR_INFO": "cyan",
    "CLI_STYLE_INFO": "",
    "CLI_COLOR_MUTED": "",
    "CLI_STYLE_MUTED": "faint",
    "CLI_COLOR_TODO_PROJECT": "yellow",
    "CLI_COLOR_TODO_CONTEXT": "cyan",
    "CLI_COLOR_TODO_KEYVAL": "magenta",
}

_LIGHT: dict[str, str] = {
    # LLM UI — dark foregrounds on a light terminal; the title bar keeps its own
    # colored band (white on blue) so it stays legible regardless of terminal bg.
    "LLM_UI_STYLE_TITLE_BAR": "#ffffff",
    "LLM_UI_STYLE_TITLE_BAR_BG": "ansiblue",
    "LLM_UI_STYLE_INFO_BAR": "#1a1a1a",
    "LLM_UI_STYLE_FRAME": "#999999",
    "LLM_UI_STYLE_FRAME_LABEL": "#0057d8",
    "LLM_UI_STYLE_INPUT_FRAME": "#999999",
    "LLM_UI_STYLE_PROMPT": "ansiblue",
    "LLM_UI_STYLE_THINKING": "ansigreen",
    "LLM_UI_STYLE_CONFIRMATION": "#b58900",
    "LLM_UI_STYLE_FAINT": "#999999",
    "LLM_UI_STYLE_OUTPUT_FIELD": "#1a1a1a",
    "LLM_UI_STYLE_INPUT_FIELD": "#1a1a1a",
    "LLM_UI_STYLE_TEXT": "#1a1a1a",
    "LLM_UI_STYLE_STATUS": "ansiblack",
    "LLM_UI_STYLE_BOTTOM_TOOLBAR": "noinherit",
    "LLM_UI_STYLE_CHOICE_BG": "#e8e8e8",
    "LLM_UI_STYLE_CHOICE_SELECTED_BG": "#b3d4fc",
    "LLM_UI_STYLE_MODE_NORMAL": "fg:ansigreen",
    "LLM_UI_STYLE_MODE_ACCEPT_EDITS": "fg:#b58900 bold",
    "LLM_UI_STYLE_MODE_PLAN": "fg:ansiblue bold",
    "LLM_UI_STYLE_MODE_YOLO": "fg:ansired bold",
    "LLM_UI_STYLE_MODE_CUSTOM": "fg:#b58900 bold",
    "LLM_UI_STYLE_INFO_YOLO_ON": "ansired",
    "LLM_UI_STYLE_INFO_YOLO_PARTIAL": "#b58900",
    "LLM_UI_STYLE_INFO_YOLO_OFF": "ansigreen",
    "LLM_UI_STYLE_INFO_PLAN_ON": "ansiblue",
    "LLM_UI_STYLE_INFO_PLAN_OFF": "ansigreen",
    # Markdown rendering
    "LLM_UI_STYLE_MARKDOWN_LINK": "bold blue underline",
    "LLM_UI_STYLE_MARKDOWN_LINK_URL": "italic blue underline",
    "LLM_UI_STYLE_MARKDOWN_H1": "bold magenta",
    "LLM_UI_STYLE_MARKDOWN_CODE": "bold #af005f",
    # CLI semantic colors/styles — avoid pale yellow/cyan on white.
    "CLI_COLOR_WARNING": "dark_orange",
    "CLI_STYLE_WARNING": "bold",
    "CLI_COLOR_ERROR": "red",
    "CLI_STYLE_ERROR": "bold",
    "CLI_COLOR_SUCCESS": "green",
    "CLI_STYLE_SUCCESS": "",
    "CLI_COLOR_HIGHLIGHT": "dark_orange",
    "CLI_STYLE_HIGHLIGHT": "bold",
    "CLI_COLOR_INFO": "blue",
    "CLI_STYLE_INFO": "",
    "CLI_COLOR_MUTED": "",
    "CLI_STYLE_MUTED": "faint",
    "CLI_COLOR_TODO_PROJECT": "dark_orange",
    "CLI_COLOR_TODO_CONTEXT": "blue",
    "CLI_COLOR_TODO_KEYVAL": "magenta",
}

THEMES: dict[str, dict[str, str]] = {"dark": _DARK, "light": _LIGHT}


def register_theme(name: str, values: dict[str, str]) -> None:
    """Register (or replace) a named theme preset.

    *values* maps style-knob names to their default value under this theme. It
    is layered **on top of the default (``dark``) palette**, so a partial theme
    only needs to specify the knobs it changes — every unspecified knob keeps
    its ``dark`` value instead of blanking. Intended for ``zrb_init.py``::

        from zrb.config.theme import register_theme

        # Only override what differs from dark; the rest is inherited.
        register_theme("solarized", {
            "CLI_COLOR_INFO": "#268bd2",
            "LLM_UI_STYLE_TEXT": "#657b83",
        })
        # then: export ZRB_THEME=solarized

    Knob names are the ``LLM_UI_STYLE_*`` / ``CLI_COLOR_*`` / ``CLI_STYLE_*``
    attribute names (see :data:`_DARK` for the full list). Values are whatever
    the knob's consumer expects: prompt_toolkit style strings for the TUI, Rich
    style strings for markdown/CLI colors.
    """
    THEMES[name] = {**_DARK, **values}


def get_theme(name: str) -> dict[str, str]:
    """Return the palette for *name*, falling back to the default theme.

    An unknown name logs a warning (so a misspelled ``ZRB_THEME`` is
    diagnosable) and resolves to :data:`DEFAULT_THEME`.
    """
    theme = THEMES.get(name)
    if theme is None:
        # Warn once per name, marking seen *before* logging: the root logger's
        # formatter styles the record via themed CLI_COLOR_* knobs, which
        # re-enter get_theme(name) — the guard breaks that recursion.
        if name not in _WARNED_UNKNOWN:
            _WARNED_UNKNOWN.add(name)
            _LOGGER.warning(
                "Unknown theme %r; falling back to %r. Known themes: %s",
                name,
                DEFAULT_THEME,
                sorted(THEMES),
            )
        return THEMES[DEFAULT_THEME]
    return theme


def theme_value(name: str, key: str) -> str:
    """Resolve a single *key* under theme *name* (``""`` if absent)."""
    return get_theme(name).get(key, "")


def theme_default(key: str):
    """Return an ``EnvField`` ``default_factory`` that resolves *key* from the
    host config's active :attr:`THEME`. Used to wire every themed style knob."""
    return lambda host: theme_value(host.THEME, key)

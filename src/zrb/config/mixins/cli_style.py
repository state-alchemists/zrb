"""CLI semantic color/style config.

Defaults come from the active theme (``CFG.THEME`` → ``config/theme.py``); an
explicitly set ``ZRB_CLI_*`` env overrides the theme.
"""

from __future__ import annotations

from zrb.config.env_field import EnvField
from zrb.config.theme import theme_default


class CLIStyleMixin:
    CLI_COLOR_WARNING = EnvField(
        str,
        default_factory=theme_default("CLI_COLOR_WARNING"),
        doc="Foreground color for warning messages (Rich color name or hex).",
    )
    CLI_STYLE_WARNING = EnvField(
        str,
        default_factory=theme_default("CLI_STYLE_WARNING"),
        doc="Text style for warning messages (e.g. bold, faint).",
    )
    CLI_COLOR_ERROR = EnvField(
        str,
        default_factory=theme_default("CLI_COLOR_ERROR"),
        doc="Foreground color for error messages.",
    )
    CLI_STYLE_ERROR = EnvField(
        str,
        default_factory=theme_default("CLI_STYLE_ERROR"),
        doc="Text style for error messages.",
    )
    CLI_COLOR_SUCCESS = EnvField(
        str,
        default_factory=theme_default("CLI_COLOR_SUCCESS"),
        doc="Foreground color for success messages.",
    )
    CLI_STYLE_SUCCESS = EnvField(
        str,
        default_factory=theme_default("CLI_STYLE_SUCCESS"),
        doc="Text style for success messages.",
    )
    CLI_COLOR_HIGHLIGHT = EnvField(
        str,
        default_factory=theme_default("CLI_COLOR_HIGHLIGHT"),
        doc="Foreground color for highlighted output.",
    )
    CLI_STYLE_HIGHLIGHT = EnvField(
        str,
        default_factory=theme_default("CLI_STYLE_HIGHLIGHT"),
        doc="Text style for highlighted output.",
    )
    CLI_COLOR_INFO = EnvField(
        str,
        default_factory=theme_default("CLI_COLOR_INFO"),
        doc="Foreground color for informational output.",
    )
    CLI_STYLE_INFO = EnvField(
        str,
        default_factory=theme_default("CLI_STYLE_INFO"),
        doc="Text style for informational output.",
    )
    CLI_COLOR_MUTED = EnvField(
        str,
        default_factory=theme_default("CLI_COLOR_MUTED"),
        doc="Foreground color for de-emphasized (muted) output.",
    )
    CLI_STYLE_MUTED = EnvField(
        str,
        default_factory=theme_default("CLI_STYLE_MUTED"),
        doc="Text style for de-emphasized output.",
    )
    CLI_COLOR_TODO_PROJECT = EnvField(
        str,
        default_factory=theme_default("CLI_COLOR_TODO_PROJECT"),
        doc="Foreground color for todo project tags (+tag).",
    )
    CLI_COLOR_TODO_CONTEXT = EnvField(
        str,
        default_factory=theme_default("CLI_COLOR_TODO_CONTEXT"),
        doc="Foreground color for todo context tags (@tag).",
    )
    CLI_COLOR_TODO_KEYVAL = EnvField(
        str,
        default_factory=theme_default("CLI_COLOR_TODO_KEYVAL"),
        doc="Foreground color for todo key:value pairs.",
    )

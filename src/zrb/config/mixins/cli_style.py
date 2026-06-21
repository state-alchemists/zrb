"""CLI semantic color/style config."""

from __future__ import annotations

from zrb.config.env_field import EnvField


class CLIStyleMixin:
    def __init__(self) -> None:
        self.DEFAULT_CLI_COLOR_WARNING: str = "yellow"
        self.DEFAULT_CLI_STYLE_WARNING: str = "bold"
        self.DEFAULT_CLI_COLOR_ERROR: str = "red"
        self.DEFAULT_CLI_STYLE_ERROR: str = "bold"
        self.DEFAULT_CLI_COLOR_SUCCESS: str = "green"
        self.DEFAULT_CLI_STYLE_SUCCESS: str = ""
        self.DEFAULT_CLI_COLOR_HIGHLIGHT: str = "yellow"
        self.DEFAULT_CLI_STYLE_HIGHLIGHT: str = "bold"
        self.DEFAULT_CLI_COLOR_INFO: str = "cyan"
        self.DEFAULT_CLI_STYLE_INFO: str = ""
        self.DEFAULT_CLI_COLOR_MUTED: str = ""
        self.DEFAULT_CLI_STYLE_MUTED: str = "faint"
        self.DEFAULT_CLI_COLOR_TODO_PROJECT: str = "yellow"
        self.DEFAULT_CLI_COLOR_TODO_CONTEXT: str = "cyan"
        self.DEFAULT_CLI_COLOR_TODO_KEYVAL: str = "magenta"
        super().__init__()

    CLI_COLOR_WARNING = EnvField(str)
    CLI_STYLE_WARNING = EnvField(str)
    CLI_COLOR_ERROR = EnvField(str)
    CLI_STYLE_ERROR = EnvField(str)
    CLI_COLOR_SUCCESS = EnvField(str)
    CLI_STYLE_SUCCESS = EnvField(str)
    CLI_COLOR_HIGHLIGHT = EnvField(str)
    CLI_STYLE_HIGHLIGHT = EnvField(str)
    CLI_COLOR_INFO = EnvField(str)
    CLI_STYLE_INFO = EnvField(str)
    CLI_COLOR_MUTED = EnvField(str)
    CLI_STYLE_MUTED = EnvField(str)
    CLI_COLOR_TODO_PROJECT = EnvField(str)
    CLI_COLOR_TODO_CONTEXT = EnvField(str)
    CLI_COLOR_TODO_KEYVAL = EnvField(str)

"""Screenshot config for the `/screenshot` command and `TakeScreenshot` tool."""

from __future__ import annotations

from zrb.config.env_field import EnvField, comma_join, comma_list, on_off
from zrb.util.string.conversion import to_boolean


class LLMScreenshotMixin:
    ENV_PREFIX: str

    def __init__(self):
        self.DEFAULT_LLM_SCREENSHOT_COMMANDS: str = "/screenshot, /ss"
        self.DEFAULT_LLM_SCREENSHOT_BACKEND: str = "auto"
        self.DEFAULT_LLM_SCREENSHOT_DISPLAY: str = ""
        self.DEFAULT_LLM_SCREENSHOT_TIMEOUT: str = "15"
        self.DEFAULT_LLM_SCREENSHOT_ENABLE_TOOL: str = "off"
        super().__init__()

    LLM_SCREENSHOT_COMMANDS = EnvField(
        comma_list,
        serialize=comma_join,
        doc=(
            "Comma-separated command aliases to capture the screen and attach "
            "it to the next message (usage: {cmd} [display]). Empty leaves "
            "the command out."
        ),
    )

    LLM_SCREENSHOT_BACKEND = EnvField(
        str,
        doc=(
            "Screenshot backend. One of:\n"
            "- 'auto' (default): the platform's chain -- screencapture on "
            "macOS; Pillow, then powershell on Windows; powershell.exe on "
            "WSL; grim, gnome-screenshot, spectacle on Wayland; Pillow, scrot, "
            "import, gnome-screenshot, spectacle on X11.\n"
            "- 'pillow': Pillow's ImageGrab (Windows, X11).\n"
            "- one capture program: 'screencapture', 'powershell', "
            "'powershell.exe', 'grim', 'gnome-screenshot', 'spectacle', "
            "'scrot', 'import'."
        ),
    )

    LLM_SCREENSHOT_DISPLAY = EnvField(
        str,
        doc=(
            "Screen captured when the command names none. Empty captures the "
            "main screen. macOS: a display number (1 is the main one); "
            "Wayland with grim: an output name such as eDP-1; Windows and "
            "WSL: 'all' for every screen; X11: an X display such as :1. "
            "Other programs capture what they always do."
        ),
    )

    LLM_SCREENSHOT_TIMEOUT = EnvField(
        float,
        fallback=15.0,
        doc=(
            "Seconds a capture may take, every program tried included, "
            "before it is abandoned. 0 means no limit. Default: 15."
        ),
    )

    LLM_SCREENSHOT_ENABLE_TOOL = EnvField(
        to_boolean,
        serialize=on_off,
        doc=(
            "Give the agent a TakeScreenshot tool, so it can look at the "
            "screen on its own instead of waiting for the screenshot "
            "command. Each call asks for approval, and plan mode denies it. "
            "Default: off."
        ),
    )

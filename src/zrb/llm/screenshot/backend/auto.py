"""The capture chain for the platform zrb runs on.

  macOS   : screencapture
  Windows : Pillow (Win32)  →  powershell
  WSL     : powershell.exe (the Windows desktop, through interop)
  Wayland : grim  →  gnome-screenshot  →  spectacle
  X11     : Pillow (XCB)  →  scrot  →  import  →  gnome-screenshot  →  spectacle
  Termux  : none; Android lets no app capture the screen without root or adb

A Wayland session never falls back to the X11 grabbers: through XWayland
they see only X clients, and would hand the model a black or partial screen
instead of failing.
"""

from __future__ import annotations

import os
import sys

from zrb.llm.screenshot.backend.any_screenshot_backend import AnyScreenshotBackend
from zrb.llm.screenshot.backend.pillow import PillowScreenshotBackend
from zrb.llm.screenshot.backend.tool import (
    GNOME_SCREENSHOT,
    GRIM,
    IMPORT,
    POWERSHELL,
    POWERSHELL_EXE,
    SCREENCAPTURE,
    SCROT,
    SPECTACLE,
    ScreenshotTool,
    ScreenshotToolBackend,
)
from zrb.llm.util.deadline import create_deadline
from zrb.util.platform import is_termux, is_wsl

ChainBackend = PillowScreenshotBackend | ScreenshotToolBackend

_MACOS_HINT = (
    "  Grant your terminal app Screen Recording in System Settings > Privacy "
    "& Security > Screen & System Audio Recording, then restart the "
    "terminal. macOS asks the first time a screen is captured; a screenshot "
    "showing only the wallpaper means the same.\n"
)
_WINDOWS_HINT = (
    "  Capture needs an unlocked, interactive desktop: it fails over SSH or "
    "from a service.\n"
)
_WSL_HINT = (
    "  zrb captures the Windows desktop through powershell.exe. Check that "
    "`which powershell.exe` finds it; if not, enable WSL interop "
    "([interop] enabled=true in /etc/wsl.conf) and run `wsl --shutdown`.\n"
)
_WAYLAND_HINT = (
    "  Install grim (sway, Hyprland and other wlroots compositors). On GNOME "
    "use gnome-screenshot, on KDE spectacle.\n"
)
_X11_HINT = "  Install scrot or ImageMagick (`import`).\n"
_NO_SESSION_HINT = (
    "  No graphical session: DISPLAY and WAYLAND_DISPLAY are unset (over "
    "SSH, say). Capture from a terminal inside the desktop session.\n"
)
_TERMUX_HINT = (
    "  Android lets no app capture the screen without root or adb. Take the "
    "screenshot on the phone and attach it with /attach.\n"
)


class AutoScreenshotBackend(AnyScreenshotBackend):
    """Each capture program the platform offers, in turn, until one delivers.
    All attempts together take at most *timeout* seconds; ``0`` means no
    limit."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout
        self._tried: list[ChainBackend] = []

    @property
    def name(self) -> str:
        return "auto"

    async def capture(self, display: str | None) -> bytes | None:
        deadline = create_deadline(self._timeout)
        self._tried = []
        for backend in self._create_chain():
            self._tried.append(backend)
            data = await backend.capture_by(display, deadline)
            if data is not None:
                return data
        return None

    def _create_chain(self) -> list[ChainBackend]:
        return [
            (
                PillowScreenshotBackend(self._timeout)
                if tool is None
                else ScreenshotToolBackend(tool, self._timeout)
            )
            for tool in _get_platform_chain()
        ]

    def list_displays(self) -> list[str]:
        if is_termux():
            return []
        if sys.platform == "darwin":
            return ["1", "2"]
        if sys.platform == "win32" or is_wsl():
            return ["all"]
        return []

    def get_failure_hint(self) -> str:
        hint = _get_platform_hint()
        for backend in self._tried:
            hint += backend.get_failure_hint()
        return hint


def _get_platform_chain() -> "list[ScreenshotTool | None]":
    """The capture programs to try, in order; ``None`` stands for Pillow."""
    if is_termux():
        return []
    if sys.platform == "darwin":
        return [SCREENCAPTURE]
    if sys.platform == "win32":
        return [None, POWERSHELL]
    if is_wsl():
        return [POWERSHELL_EXE]
    if _is_wayland():
        return [GRIM, GNOME_SCREENSHOT, SPECTACLE]
    if os.environ.get("DISPLAY"):
        return [None, SCROT, IMPORT, GNOME_SCREENSHOT, SPECTACLE]
    return []


def _get_platform_hint() -> str:
    if is_termux():
        return _TERMUX_HINT
    if sys.platform == "darwin":
        return _MACOS_HINT
    if sys.platform == "win32":
        return _WINDOWS_HINT
    if is_wsl():
        return _WSL_HINT
    if _is_wayland():
        return _WAYLAND_HINT
    if os.environ.get("DISPLAY"):
        return _X11_HINT
    return _NO_SESSION_HINT


def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY")) or (
        os.environ.get("XDG_SESSION_TYPE") == "wayland"
    )

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.screenshot.backend.any_screenshot_backend import AnyScreenshotBackend
from zrb.llm.screenshot.backend.auto import AutoScreenshotBackend
from zrb.llm.screenshot.backend.pillow import PillowScreenshotBackend
from zrb.llm.screenshot.backend.tool import SCREENSHOT_TOOLS, ScreenshotToolBackend

if TYPE_CHECKING:
    from zrb.llm.screenshot.config import ScreenshotConfig


def get_screenshot_backend(
    backend: "str | AnyScreenshotBackend", config: "ScreenshotConfig"
) -> AnyScreenshotBackend:
    """*backend* itself, or the built-in one it names, built from the resolved
    *config*: ``auto`` (the platform's chain), ``pillow``, or one capture
    program (``screencapture``, ``powershell``, ``powershell.exe``, ``grim``,
    ``gnome-screenshot``, ``spectacle``, ``scrot``, ``import``)."""
    if isinstance(backend, AnyScreenshotBackend):
        return backend
    name = backend.strip().lower() or "auto"
    timeout = config.timeout or 0.0
    if name == "auto":
        return AutoScreenshotBackend(timeout)
    if name == "pillow":
        return PillowScreenshotBackend(timeout)
    if name in SCREENSHOT_TOOLS:
        return ScreenshotToolBackend(SCREENSHOT_TOOLS[name], timeout)
    names = ", ".join(["auto", "pillow", *SCREENSHOT_TOOLS])
    raise ValueError(
        f"unknown screenshot backend {backend!r}: use {names}, "
        "or an AnyScreenshotBackend"
    )

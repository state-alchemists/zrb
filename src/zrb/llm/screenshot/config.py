from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.util.feature_config import resolve_from_cfg

if TYPE_CHECKING:
    from zrb.llm.screenshot.backend.any_screenshot_backend import (
        AnyScreenshotBackend,
    )


@dataclass
class ScreenshotConfig:
    """Settings for `enable_screenshot`. Each field mirrors
    `CFG.LLM_SCREENSHOT_<FIELD>`; one left ``None`` is read from there when a
    session starts.

    *enable_tool* adds the `TakeScreenshot` tool beside the command; an empty
    *commands* list leaves the command out, so either can be had without the
    other.

    *backend* names a built-in backend (``auto``, ``pillow``, or a capture
    program such as ``grim``) or is an `AnyScreenshotBackend` of your own.
    """

    commands: list[str] | None = None
    backend: "str | AnyScreenshotBackend | None" = None
    display: str | None = None
    timeout: float | None = None
    enable_tool: bool | None = None

    def resolve(self) -> "ScreenshotConfig":
        """A copy with every ``None`` field read from `CFG`."""
        return resolve_from_cfg(self, "LLM_SCREENSHOT_")

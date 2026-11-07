from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.llm.shared.feature_config import accepts_renamed_fields, resolve_from_cfg

if TYPE_CHECKING:
    from zrb.llm.screenshot.backend.any_screenshot_backend import (
        AnyScreenshotBackend,
    )


@accepts_renamed_fields(enable_tool="tool_enabled")
@dataclass
class ScreenshotConfig:
    """Settings for `enable_screenshot`. Each field mirrors
    `CFG.LLM_SCREENSHOT_<FIELD>`; one left ``None`` is read from there when a
    session starts.

    *tool_enabled* adds the `TakeScreenshot` tool beside the command; an empty
    *commands* list leaves the command out, so either can be had without the
    other. ``enable_tool``, its name before the switch suffix, still works and
    warns.

    *backend* names a built-in backend (``auto``, ``pillow``, or a capture
    program such as ``grim``) or is an `AnyScreenshotBackend` of your own.
    """

    commands: list[str] | None = None
    backend: "str | AnyScreenshotBackend | None" = None
    display: str | None = None
    timeout: float | None = None
    tool_enabled: bool | None = None

    def resolve(self) -> "ScreenshotConfig":
        """A copy with every ``None`` field read from `CFG`."""
        return resolve_from_cfg(self, "LLM_SCREENSHOT_")

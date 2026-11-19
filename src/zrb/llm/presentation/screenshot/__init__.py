"""Screen capture for chat sessions: `enable_screenshot` adds
`/screenshot [display]` and, opted in, the `TakeScreenshot` tool."""

from zrb.llm.presentation.screenshot.backend import (
    AnyScreenshotBackend,
    AutoScreenshotBackend,
    PillowScreenshotBackend,
    ScreenshotTool,
    ScreenshotToolBackend,
)
from zrb.llm.presentation.screenshot.config import ScreenshotConfig
from zrb.llm.presentation.screenshot.feature import enable_screenshot

__all__ = [
    "AnyScreenshotBackend",
    "AutoScreenshotBackend",
    "PillowScreenshotBackend",
    "ScreenshotConfig",
    "ScreenshotTool",
    "ScreenshotToolBackend",
    "enable_screenshot",
]

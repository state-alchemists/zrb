"""Screen capture for chat sessions: `enable_screenshot` adds
`/screenshot [display]` and, opted in, the `TakeScreenshot` tool."""

from zrb.llm.screenshot.backend import (
    AnyScreenshotBackend,
    AutoScreenshotBackend,
    PillowScreenshotBackend,
    ScreenshotTool,
    ScreenshotToolBackend,
)
from zrb.llm.screenshot.config import ScreenshotConfig
from zrb.llm.screenshot.feature import enable_screenshot

__all__ = [
    "AnyScreenshotBackend",
    "AutoScreenshotBackend",
    "PillowScreenshotBackend",
    "ScreenshotConfig",
    "ScreenshotTool",
    "ScreenshotToolBackend",
    "enable_screenshot",
]

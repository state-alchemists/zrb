"""Screen capture through Pillow's `ImageGrab`: the Win32 screen on Windows,
the X server on X11. Pillow is a zrb dependency, so neither needs a program
installed.

`ImageGrab.grab` is given the X display explicitly, so on Linux it never
falls back to the external programs it would otherwise run without a time
limit; those are `ScreenshotToolBackend`'s job.
"""

from __future__ import annotations

import asyncio
import io
import os
import sys

from zrb.llm.screenshot.backend.any_screenshot_backend import AnyScreenshotBackend
from zrb.llm.util.deadline import create_deadline, get_earlier, get_remaining


class PillowScreenshotBackend(AnyScreenshotBackend):
    """`ImageGrab.grab`. On Windows a display of ``all`` captures every
    screen; on X11 a display is the X server (``:0``). A capture taking over
    *timeout* seconds is abandoned; ``0`` means no limit."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout
        self._last_error: str | None = None

    @property
    def name(self) -> str:
        return "pillow"

    @property
    def last_error(self) -> str | None:
        """Why the last capture failed, or ``None`` after a success."""
        return self._last_error

    async def capture(self, display: str | None) -> bytes | None:
        return await self.capture_by(display, None)

    async def capture_by(
        self, display: str | None, deadline: float | None
    ) -> bytes | None:
        """`capture`, giving up at *deadline* (`time.monotonic()`) or after
        this backend's own timeout, whichever comes first."""
        deadline = get_earlier(deadline, create_deadline(self._timeout))
        self._last_error = None
        timeout = get_remaining(deadline)
        if timeout == 0:
            self._last_error = "no time left for this capture"
            return None
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_grab, display), timeout=timeout
            )
        except asyncio.TimeoutError:
            self._last_error = f"timed out after {timeout:.1f}s"
        except (OSError, ValueError) as error:
            self._last_error = str(error) or type(error).__name__
        return None

    def get_failure_hint(self) -> str:
        if self._last_error:
            return f"  {self.name}: {self._last_error}\n"
        return ""


def _grab(display: str | None) -> bytes:
    # lazy: heavy third-party — Pillow, needed only when a screen is captured
    from PIL import ImageGrab

    if sys.platform == "win32":
        image = ImageGrab.grab(all_screens=display == "all")
    else:
        x_display = display or os.environ.get("DISPLAY")
        if not x_display:
            raise OSError(
                "no X display to capture: DISPLAY is unset and no display was named"
            )
        image = ImageGrab.grab(xdisplay=x_display)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()

"""Screen capture through Pillow's `ImageGrab`: the Win32 screen on Windows,
the X server on X11. Pillow is a zrb dependency, so neither needs a program
installed.

The grab runs in a subprocess (`sys.executable -c` running `ImageGrab`),
*not* in `asyncio.to_thread`: `wait_for` cancelling a thread cannot stop
the blocked `ImageGrab.grab`, so a timed-out capture would leave a worker
thread tied up in the shared asyncio executor. A subprocess is killed on
timeout instead (`communicate_within` calls `proc.kill()`), so repeated
timed-out captures cannot accumulate.

`ImageGrab.grab` is given the X display explicitly, so on Linux it never
falls back to the external programs it would otherwise run without a time
limit; those are `ScreenshotToolBackend`'s job.
"""

from __future__ import annotations

import sys

from zrb.llm.screenshot.backend.any_screenshot_backend import AnyScreenshotBackend
from zrb.llm.screenshot.backend.program import ProgramFailed, run_program
from zrb.llm.util.deadline import create_deadline, get_earlier

# Runs in a subprocess: `-c` with this source, the display as argv[1]. Kept
# out of the shared asyncio thread pool so a timed-out grab is killable.
_GRAB = """import io, os, sys
from PIL import ImageGrab

display = sys.argv[1] if len(sys.argv) > 1 else ""
if sys.platform == "win32":
    image = ImageGrab.grab(all_screens=display == "all")
else:
    x_display = display or os.environ.get("DISPLAY")
    if not x_display:
        sys.stderr.write("no X display to capture: DISPLAY is unset and no display was named\\n")
        sys.exit(1)
    image = ImageGrab.grab(xdisplay=x_display)
buffer = io.BytesIO()
image.convert("RGB").save(buffer, format="JPEG", quality=90)
sys.stdout.buffer.write(buffer.getvalue())
"""


class PillowScreenshotBackend(AnyScreenshotBackend):
    """`ImageGrab.grab`, run in a subprocess. On Windows a display of
    ``all`` captures every screen; on X11 a display is the X server
    (``:0``). A capture taking over *timeout* seconds is abandoned and the
    subprocess is killed; ``0`` means no limit."""

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
        try:
            stdout = await run_program(
                [sys.executable, "-c", _GRAB, display or ""], deadline
            )
        except ProgramFailed as error:
            self._last_error = str(error)
            return None
        return stdout or None

    def get_failure_hint(self) -> str:
        if self._last_error:
            return f"  {self.name}: {self._last_error}\n"
        return ""

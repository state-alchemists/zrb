"""Screen capture through one external program: `screencapture` on macOS,
`powershell` on Windows and WSL, `grim`, `gnome-screenshot` and `spectacle`
on Wayland, `scrot` and ImageMagick's `import` on X11.

Every program but PowerShell writes a file; each capture gets its own
temporary directory, removed afterwards whatever happened, so a failed
capture never returns an earlier screen and nothing is left behind.
"""

from __future__ import annotations

import base64
import binascii
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass

from zrb.config.config import CFG
from zrb.llm.screenshot.backend.any_screenshot_backend import AnyScreenshotBackend
from zrb.llm.screenshot.backend.program import ProgramFailed, run_program
from zrb.llm.util.deadline import create_deadline, get_earlier


@dataclass(frozen=True)
class ScreenshotTool:
    """How to run one capture program.

    *create_args* maps ``(path, display)`` to the arguments after
    *executable*; *path* is empty for a tool that prints the image to stdout
    as base64 (*to_stdout*). With *uses_x_display*, a display is passed as
    the X server to talk to (``DISPLAY``) rather than as an argument.
    """

    name: str
    executable: str
    create_args: Callable[[str, str | None], list[str]]
    suffix: str = ".jpg"
    to_stdout: bool = False
    uses_x_display: bool = False


class ScreenshotToolBackend(AnyScreenshotBackend):
    """Runs *tool*. A capture taking over *timeout* seconds is abandoned;
    ``0`` means no limit."""

    def __init__(self, tool: ScreenshotTool, timeout: float = 15.0) -> None:
        self._tool = tool
        self._timeout = timeout
        self._last_error: str | None = None

    @property
    def name(self) -> str:
        return self._tool.name

    @property
    def is_available(self) -> bool:
        return shutil.which(self._tool.executable) is not None

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
        if not self.is_available:
            self._last_error = f"`{self._tool.executable}` is not installed"
            return None
        if self._tool.to_stdout:
            return await self._run_to_stdout(display, deadline)
        with tempfile.TemporaryDirectory(
            prefix=f"{CFG.ROOT_GROUP_NAME}_screenshot_"
        ) as directory:
            path = os.path.join(directory, f"screen{self._tool.suffix}")
            args = self._tool.create_args(path, display)
            if await self._run(args, display, deadline) is None:
                return None
            data = _read(path)
        if data is None:
            self._last_error = "exited without writing an image"
        return data

    async def _run_to_stdout(
        self, display: str | None, deadline: float | None
    ) -> bytes | None:
        stdout = await self._run(self._tool.create_args("", display), display, deadline)
        if stdout is None:
            return None
        try:
            return base64.b64decode(stdout.strip(), validate=True) or None
        except (binascii.Error, ValueError):
            self._last_error = "printed something that is not a base64 image"
            return None

    async def _run(
        self, args: list[str], display: str | None, deadline: float | None
    ) -> bytes | None:
        """The program's stdout when it exits 0, else ``None`` with
        `last_error` set."""
        try:
            return await run_program(
                [self._tool.executable, *args], deadline, self._get_env(display)
            )
        except ProgramFailed as error:
            self._last_error = str(error)
            return None

    def _get_env(self, display: str | None) -> dict[str, str] | None:
        if not (display and self._tool.uses_x_display):
            return None
        return {**os.environ, "DISPLAY": display}

    def get_failure_hint(self) -> str:
        if self._last_error:
            return f"  {self.name}: {self._last_error}\n"
        return ""


def _read(path: str) -> bytes | None:
    try:
        with open(path, "rb") as image_file:
            return image_file.read() or None
    except OSError:
        return None


def _screencapture_args(path: str, display: str | None) -> list[str]:
    # -x: no shutter sound. -D picks a display by number; 1 is the main one.
    display_args = ["-D", display] if display else []
    return ["-x", "-t", "jpg", *display_args, path]


def _grim_args(path: str, display: str | None) -> list[str]:
    output_args = ["-o", display] if display else []
    return ["-t", "jpeg", *output_args, path]


def _gnome_screenshot_args(path: str, display: str | None) -> list[str]:
    return ["-f", path]


def _spectacle_args(path: str, display: str | None) -> list[str]:
    # Background, no notification, every screen, written to path.
    return ["-b", "-n", "-f", "-o", path]


def _scrot_args(path: str, display: str | None) -> list[str]:
    return [path]


def _import_args(path: str, display: str | None) -> list[str]:
    return ["-window", "root", path]


# PowerShell draws the screen into a bitmap through System.Drawing and prints
# it as base64, so nothing crosses the Windows/WSL file systems. Without
# SetProcessDPIAware a scaled display would be captured only in part.
_POWERSHELL_SCRIPT = """
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
Add-Type -Name Dpi -Namespace Zrb -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
[void][Zrb.Dpi]::SetProcessDPIAware()
$b = {bounds}
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$ms = New-Object System.IO.MemoryStream
$bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Jpeg)
[Convert]::ToBase64String($ms.ToArray())
"""


def _powershell_args(path: str, display: str | None) -> list[str]:
    bounds = (
        "[System.Windows.Forms.SystemInformation]::VirtualScreen"
        if display == "all"
        else "[System.Windows.Forms.Screen]::PrimaryScreen.Bounds"
    )
    script = _POWERSHELL_SCRIPT.replace("{bounds}", bounds)
    return ["-NoProfile", "-NonInteractive", "-Command", script]


SCREENCAPTURE = ScreenshotTool("screencapture", "screencapture", _screencapture_args)
GRIM = ScreenshotTool("grim", "grim", _grim_args)
GNOME_SCREENSHOT = ScreenshotTool(
    "gnome-screenshot", "gnome-screenshot", _gnome_screenshot_args, suffix=".png"
)
SPECTACLE = ScreenshotTool("spectacle", "spectacle", _spectacle_args, suffix=".png")
SCROT = ScreenshotTool("scrot", "scrot", _scrot_args, uses_x_display=True)
IMPORT = ScreenshotTool("import", "import", _import_args, uses_x_display=True)
POWERSHELL = ScreenshotTool(
    "powershell", "powershell", _powershell_args, to_stdout=True
)
# The Windows PowerShell WSL reaches through interop.
POWERSHELL_EXE = ScreenshotTool(
    "powershell.exe", "powershell.exe", _powershell_args, to_stdout=True
)

SCREENSHOT_TOOLS: dict[str, ScreenshotTool] = {
    tool.name: tool
    for tool in (
        SCREENCAPTURE,
        GRIM,
        GNOME_SCREENSHOT,
        SPECTACLE,
        SCROT,
        IMPORT,
        POWERSHELL,
        POWERSHELL_EXE,
    )
}

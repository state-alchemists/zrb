"""
Cross-platform clipboard image reading.

Priority order per platform:
  macOS   : Pillow ImageGrab  →  osascript fallback
  Windows : Pillow ImageGrab  (only option; shows hint if Pillow missing)
  Linux   : wl-paste (Wayland) or xclip (X11) via subprocess
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import tempfile


async def get_clipboard_image() -> bytes | None:
    """
    Try to read an image from the system clipboard.

    Returns raw PNG bytes if the clipboard contains an image, otherwise None.
    Never raises — errors are swallowed and None is returned.
    """
    try:
        if sys.platform == "darwin":
            return await _macos()
        if sys.platform == "win32":
            return _windows()
        return await _linux()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


async def _macos() -> bytes | None:
    try:
        from PIL import ImageGrab  # type: ignore[import]

        img = await asyncio.to_thread(ImageGrab.grabclipboard)
        if img is None:
            return None
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        return await _macos_osascript()


async def _macos_osascript() -> bytes | None:
    """Fallback: dump clipboard PNG via AppleScript when Pillow is absent."""
    tmp = os.path.join(tempfile.gettempdir(), "zrb_clipboard_img.png")
    script = (
        "try\n"
        "  set imgData to (the clipboard as \u00abclass PNGf\u00bb)\n"
        f'  set f to open for access POSIX file "{tmp}" with write permission\n'
        "  write imgData to f\n"
        "  close access f\n"
        "on error\n"
        "  try\n"
        f'    close access POSIX file "{tmp}"\n'
        "  end try\n"
        "end try"
    )
    proc = await asyncio.create_subprocess_exec(
        "osascript",
        "-e",
        script,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
        with open(tmp, "rb") as fh:
            data = fh.read()
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return data
    return None


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def _windows() -> bytes | None:
    try:
        from PIL import ImageGrab  # type: ignore[import]

        img = ImageGrab.grabclipboard()
        if img is None:
            return None
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        return None  # Pillow is required on Windows; handled by caller


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------


async def _linux() -> bytes | None:
    if os.environ.get("WAYLAND_DISPLAY"):
        data = await _run(["wl-paste", "--type", "image/png"])
        if data is not None:
            return data
        # wl-paste may not be installed — try xclip as last resort
    return await _run(["xclip", "-selection", "clipboard", "-t", "image/png", "-o"])


async def _run(cmd: list[str]) -> bytes | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout:
            return stdout
        return None
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Hint text shown in the UI when no image was found
# ---------------------------------------------------------------------------


def missing_tool_hint() -> str:
    """Return a short help string when clipboard image reading fails on Linux."""
    if sys.platform not in ("linux", "linux2"):
        return ""
    if os.environ.get("WAYLAND_DISPLAY"):
        return "  Install wl-clipboard (wl-paste) for clipboard image support.\n"
    return "  Install xclip for clipboard image support.\n"

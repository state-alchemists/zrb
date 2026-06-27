"""
Cross-platform clipboard image reading.

Priority order per platform:
  macOS   : Pillow ImageGrab  →  osascript fallback
  Windows : Pillow ImageGrab  (only option; shows hint if Pillow missing)
  WSL     : powershell.exe  →  wl-paste (multi-type)  →  xclip
  Linux   : wl-paste (Wayland, multi-type)  →  xclip (X11)
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import shutil
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
        # lazy: heavy third-party
        from PIL import ImageGrab  # type: ignore[import]

        img = await asyncio.to_thread(ImageGrab.grabclipboard)
        # grabclipboard() returns an Image, a list of file paths, or None.
        if img is None or isinstance(img, list):
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
        # lazy: heavy third-party
        from PIL import ImageGrab  # type: ignore[import]

        img = ImageGrab.grabclipboard()
        # grabclipboard() returns an Image, a list of file paths, or None.
        if img is None or isinstance(img, list):
            return None
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        return None  # Pillow is required on Windows; handled by caller


# ---------------------------------------------------------------------------
# Linux / WSL
# ---------------------------------------------------------------------------

# MIME types to try with wl-paste, in preference order.
# Windows clipboard images are often BMP/DIB, not PNG.
_WAYLAND_IMAGE_TYPES = ("image/png", "image/bmp", "image/jpeg", "image/tiff")


def _is_wsl() -> bool:
    """Return True when running inside Windows Subsystem for Linux."""
    return bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSLENV"))


async def _linux() -> bytes | None:
    # WSL: PowerShell has direct access to the Windows clipboard — most reliable.
    if _is_wsl():
        data = await _wsl_powershell()
        if data is not None:
            return data

    if os.environ.get("WAYLAND_DISPLAY"):
        # Try each MIME type; Windows clipboard images may not be PNG-typed.
        for mime_type in _WAYLAND_IMAGE_TYPES:
            data = await _run(["wl-paste", "--no-newline", "--type", mime_type])
            if data is not None:
                if mime_type != "image/png":
                    data = _to_png(data)
                if data:
                    return data

    return await _run(["xclip", "-selection", "clipboard", "-t", "image/png", "-o"])


async def _wsl_powershell() -> bytes | None:
    """Read image from Windows clipboard via powershell.exe.

    PowerShell is always available in WSL2 and has native access to the
    Windows clipboard, regardless of WAYLAND_DISPLAY / DISPLAY state.
    """
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$img=[System.Windows.Forms.Clipboard]::GetImage();"
        "if($img){"
        "$ms=New-Object System.IO.MemoryStream;"
        "$img.Save($ms,[System.Drawing.Imaging.ImageFormat]::Png);"
        "[Console]::OpenStandardOutput().Write($ms.ToArray(),0,$ms.Length)"
        "}"
    )
    for ps in ("powershell.exe", "pwsh.exe"):
        data = await _run([ps, "-NoProfile", "-NonInteractive", "-Command", script])
        if data:
            return data
    return None


def _to_png(data: bytes) -> bytes | None:
    """Convert arbitrary image bytes (e.g. BMP) to PNG using Pillow if available."""
    try:
        # lazy: heavy third-party
        from PIL import Image  # type: ignore[import]

        img = Image.open(io.BytesIO(data))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


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
# Clipboard writing
# ---------------------------------------------------------------------------


def copy_text(text: str) -> bool:
    """Copy text to system clipboard.

    Uses ``pyperclip`` (the project's existing clipboard backend) when
    available, with an OSC 52 terminal-escape fallback that works over
    SSH. Returns ``True`` if the text was successfully placed on the
    clipboard.
    """
    try:
        # lazy: heavy third-party
        import pyperclip  # type: ignore[import]

        pyperclip.copy(text)
        return True
    except Exception:
        # OSC 52 fallback — works over SSH when the terminal emulator
        # (iTerm2, GNOME Terminal, etc.) supports it.
        if sys.stdout.isatty():
            try:
                _write_osc52(text)
                return True
            except Exception:
                pass
        return False


def _write_osc52(text: str) -> None:
    """Send clipboard content via OSC 52 escape sequence.

    The terminal emulator on the *local* machine handles the clipboard,
    so this works over SSH. Tmux and screen need a passthrough wrapper.
    """
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    tmux = os.environ.get("TMUX")
    screen = os.environ.get("TERM") == "screen"
    if tmux:
        sys.stdout.write(f"\x1bPtmux;\x1b\x1b]52;c;{encoded}\x07\x1b\\")
    elif screen:
        sys.stdout.write(f"\x1bP\x1b]52;c;{encoded}\x07\x1b\\")
    else:
        sys.stdout.write(f"\x1b]52;c;{encoded}\x07")
    sys.stdout.flush()


def missing_tool_hint() -> str:
    """Return a short help string when clipboard image reading fails on Linux."""
    if sys.platform not in ("linux", "linux2"):
        return ""

    if _is_wsl():
        # powershell.exe should always be present in WSL2; if we got here it
        # means even that failed — nothing more we can suggest.
        return ""

    if os.environ.get("WAYLAND_DISPLAY"):
        # Only show the hint when wl-paste is actually missing.

        if shutil.which("wl-paste") is None:
            return "  Install wl-clipboard (wl-paste) for clipboard image support.\n"
        return ""

    if shutil.which("xclip") is None:
        return "  Install xclip for clipboard image support.\n"
    return ""

"""
Cross-platform camera photo capture.

Priority order per platform:
  Termux (native or proot) : termux-camera-photo
  macOS                    : ffmpeg (avfoundation)
  Windows                  : ffmpeg (dshow; auto-detects the first video device)
  Linux / WSL              : ffmpeg (v4l2; WSL needs usbipd-win passthrough for
                              /dev/video*)

No new Python dependency: capture shells out to already-optional external
binaries (ffmpeg, termux-camera-photo), the same approach `clipboard.py`
uses for clipboard images (wl-paste / xclip / osascript / powershell.exe).

Termux from inside a `proot-distro` guest is not special-cased: the
Termux:API app that actually captures the photo is a separate, non-prooted
Android process with its own real filesystem view, so it can only write to a
path that is valid there -- a proot guest's own `/tmp` or `$HOME` is not
(the app reports a `FileUtils Error` when asked to). Writing to a fixed
absolute path under Termux's *real* home directory works from both native
Termux and a proot guest, since that path is the same real location either
way -- no proot detection needed.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys

# Termux's real home directory is always at this fixed location, regardless
# of whether the caller is native Termux or a proot-distro guest -- see the
# module docstring and `_termux_camera_photo`.
_TERMUX_HOME_PHOTO_PATH = "/data/data/com.termux/files/home/.zrb_camera_photo.jpg"


async def get_camera_photo(device: str | None = None) -> bytes | None:
    """
    Try to capture a single JPEG photo from the system camera.

    Returns raw JPEG bytes on success, otherwise None. Never raises --
    errors are swallowed and None is returned; call `missing_tool_hint()`
    to explain the failure to the user.
    """
    try:
        # lazy: internal helper; cheap but avoids top-level import
        from zrb.config.helper import is_termux

        if is_termux() and shutil.which("termux-camera-photo"):
            data = await _termux_camera_photo(device)
            if data is not None:
                return data
        return await _ffmpeg_capture(device)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Termux
# ---------------------------------------------------------------------------


async def _termux_camera_photo(device: str | None) -> bytes | None:
    """Capture via the Termux:API camera intent. Writes to a file (no stdout support).

    The Termux:API app writes the photo from its own (real Android) process,
    not from whatever shell invoked `termux-camera-photo` -- so the target
    path must be valid in Termux's real filesystem, not `tempfile.gettempdir()`
    (which resolves to a proot guest's own `/tmp` when called from inside
    `proot-distro`, a path the app can't see). Termux's home directory is
    always at this fixed location, regardless of caller.
    """
    camera_id = device or "0"
    tmp = _TERMUX_HOME_PHOTO_PATH
    try:
        proc = await asyncio.create_subprocess_exec(
            "termux-camera-photo",
            "-c",
            camera_id,
            tmp,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
    except FileNotFoundError:
        return None
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
# ffmpeg (macOS / Windows / Linux / WSL)
# ---------------------------------------------------------------------------


async def _ffmpeg_capture(device: str | None) -> bytes | None:
    if shutil.which("ffmpeg") is None:
        return None

    if sys.platform == "darwin":
        input_fmt, input_arg = "avfoundation", device or "0"
    elif sys.platform == "win32":
        name = device or await _dshow_default_device()
        if name is None:
            return None
        input_fmt, input_arg = "dshow", f"video={name}"
    else:
        input_fmt, input_arg = "v4l2", device or "/dev/video0"

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        input_fmt,
        "-i",
        input_arg,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    return await _run(cmd)


async def _dshow_default_device() -> str | None:
    """Auto-detect the first dshow video device name via ffmpeg's device listing.

    `ffmpeg -f dshow -list_devices true -i dummy` always exits non-zero (the
    "dummy" input doesn't exist) and writes the device list to stderr.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-f",
            "dshow",
            "-list_devices",
            "true",
            "-i",
            "dummy",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
    except FileNotFoundError:
        return None
    match = re.search(r'"([^"]+)"\s*\(video\)', stderr.decode(errors="ignore"))
    return match.group(1) if match else None


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


def missing_tool_hint() -> str:
    """Return a short help string explaining why camera capture failed."""
    # lazy: internal helper; cheap but avoids top-level import
    from zrb.config.helper import is_termux

    if is_termux():
        return "  Install the Termux:API app (F-Droid) and `pkg install termux-api`.\n"
    if sys.platform == "darwin":
        return (
            "  Install ffmpeg (brew install ffmpeg) and grant your terminal "
            "app camera access in System Settings > Privacy & Security > "
            "Camera.\n"
        )
    if sys.platform == "win32":
        return (
            "  Install ffmpeg (https://ffmpeg.org) and make sure a webcam "
            "driver is installed. If detection fails, run `ffmpeg -f dshow "
            "-list_devices true -i dummy` to find your device name and pass "
            'it explicitly: /photo "<device name>".\n'
        )
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSLENV"):
        return (
            "  Install ffmpeg. WSL2 has no camera passthrough by default -- "
            "set up usbipd-win (https://github.com/dorssel/usbipd-win) to "
            "attach the webcam to the WSL2 kernel.\n"
        )
    return (
        "  Install ffmpeg. If no camera is found, check /dev/video* "
        "permissions (add your user to the `video` group).\n"
    )

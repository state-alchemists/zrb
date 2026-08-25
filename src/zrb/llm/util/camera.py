"""
Cross-platform camera photo capture.

Priority order per platform:
  Termux (native or proot) : termux-camera-photo
  macOS                    : ffmpeg (avfoundation)
  Windows                  : ffmpeg (dshow; auto-detects the first video device)
  Linux / WSL              : ffmpeg (v4l2)

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

WSL2 camera capture has two separate, layered failure modes -- see
`docs/advanced-topics/llm-integration.md#troubleshooting-voice--photo` for
the full write-up, this is the short version for future maintainers:

1. The stock `microsoft-standard-WSL2` kernel ships with *no* camera driver
   at all -- no `uvcvideo`, no v4l2 core, not even as a loadable module.
   `usbipd-win` (https://github.com/dorssel/usbipd-win) only does USB-level
   passthrough: it can get the webcam enumerated on the USB bus inside WSL2
   (visible in `lsusb`/`dmesg`) while `/dev/video0` still never appears,
   because turning a USB device into a `/dev/video*` node is the kernel
   driver's job and this kernel doesn't have one. Fixed only by building a
   custom WSL2 kernel with USB Video Class support and pointing `.wslconfig`
   at it (`kernel=`). `wsl --shutdown` force-powers-off the VM without
   flushing disk cache first -- a `make modules_install` that hasn't been
   `sync`ed to disk yet is silently lost on the next boot, so always `sync`
   (or reboot only after an idle moment) right after installing modules.
2. Even with the driver working, ffmpeg's default v4l2 negotiation asks for
   raw YUYV at the camera's max resolution (often 1080p, ~165 Mbps
   uncompressed) -- usbipd-win's USB/IP tunnel can't sustain that and the
   capture hangs indefinitely with the camera light stuck on, no frame ever
   delivered. `_ffmpeg_capture` below works around this by requesting MJPEG
   (compressed on-camera) at 640x480 first -- tested as the largest size
   that lands reliably over USB/IP; 720p MJPEG still hangs, since this is an
   isochronous-transfer reliability ceiling, not simply a bandwidth budget.
   `_run`'s capture timeout is the backstop for cameras/setups where even
   that still hangs.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import re
import shutil
import sys
import time
from typing import Any

from zrb.config.helper import is_wsl

logger = logging.getLogger(__name__)

# Termux's real home directory is always at this fixed location, regardless
# of whether the caller is native Termux or a proot-distro guest -- see the
# module docstring and `_termux_camera_photo`.
TERMUX_HOME_PHOTO_PATH = "/data/data/com.termux/files/home/.zrb_camera_photo.jpg"

# Last ffmpeg stderr tail, for `missing_tool_hint()` to surface -- `_run`'s
# caller only gets `None` on failure, so the actual reason needs a side
# channel rather than widening every call site's return type.
_last_ffmpeg_error: str | None = None


async def get_camera_photo(device: str | None = None) -> bytes | None:
    """
    Try to capture a single JPEG photo from the system camera.

    Returns raw JPEG bytes on success, otherwise None. Never raises --
    errors are swallowed and None is returned; call `missing_tool_hint()`
    to explain the failure to the user.
    """
    try:
        # lazy: tests patch zrb.config.helper.is_termux; hoisting would bind
        # the name at this module's load time and bypass the mock.
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
    tmp = TERMUX_HOME_PHOTO_PATH
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

    extra_args: list[str] = []
    if sys.platform == "darwin":
        # avfoundation defaults to 29.97fps, which many macOS cameras don't
        # support (they list only exact 15 or 30fps modes) -- ffmpeg then
        # fails to open the device with a bare "Input/output error".
        input_fmt, input_arg = "avfoundation", device or "0"
        extra_args = ["-framerate", "30"]
    elif sys.platform == "win32":
        name = device or await _dshow_default_device()
        if name is None:
            return None
        input_fmt, input_arg = "dshow", f"video={name}"
    else:
        input_fmt, input_arg = "v4l2", device or "/dev/video0"
        # v4l2 otherwise negotiates raw YUYV at the camera's max resolution
        # -- over a USB/IP tunnel (WSL2 + usbipd-win) that bandwidth hangs
        # the capture indefinitely with no frame ever written. MJPEG is
        # compressed on-camera and lands well under that ceiling; fall back
        # to the raw default for cameras that don't support it.
        # 720p MJPEG still hangs over usbipd-win's USB/IP tunnel (isochronous
        # transfer reliability, not raw bandwidth -- 720p times out even
        # compressed) -- 640x480 is the largest size that lands consistently.
        mjpeg_args = ["-input_format", "mjpeg", "-video_size", "640x480"]
        data = await _run(_ffmpeg_cmd(input_fmt, mjpeg_args, input_arg))
        if data is not None:
            return data

    return await _run(_ffmpeg_cmd(input_fmt, extra_args, input_arg))


def _ffmpeg_cmd(input_fmt: str, extra_args: list[str], input_arg: str) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-f",
        input_fmt,
        *extra_args,
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


async def _dshow_default_device() -> str | None:
    """Auto-detect the first dshow video device name via ffmpeg's device listing.

    `ffmpeg -f dshow -list_devices true -i dummy` always exits non-zero (the
    "dummy" input doesn't exist) and writes the device list to stderr.
    """
    names = await _dshow_device_names()
    return names[0] if names else None


_DSHOW_LIST_TIMEOUT_SECONDS = 5


async def _dshow_device_names() -> list[str]:
    """All dshow video device names, via ffmpeg's device listing."""
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
        try:
            _, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_DSHOW_LIST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return []
    except FileNotFoundError:
        return []
    return _parse_dshow_video_devices(stderr.decode(errors="ignore"))


def _parse_dshow_video_devices(stderr_text: str) -> list[str]:
    return re.findall(r'"([^"]+)"\s*\(video\)', stderr_text)


# ---------------------------------------------------------------------------
# Device suggestions (/photo argument completion)
# ---------------------------------------------------------------------------

_DEVICE_CACHE_TTL_SECONDS = 60
# Same cache-dict convention as `completion/caches.py`: callers may pass their
# own dict to control lifetime; the module default keeps the completer
# stateless. {"time": float, "devices": list[str], "refreshing": bool}
_default_device_cache: dict[str, Any] = {}


def _compute_camera_devices_sync() -> list[str]:
    """Cheap, non-blocking device candidates; empty where a probe is needed."""
    # lazy: tests patch zrb.config.helper.is_termux; hoisting would bind the
    # name at this module's load time and bypass the mock.
    from zrb.config.helper import is_termux

    if is_termux():
        # termux-camera-photo -c <camera_id>: front/back are typically 0/1.
        return ["0", "1"]
    if sys.platform == "darwin":
        # avfoundation device index; probing requires a full ffmpeg listing.
        return ["0", "1"]
    if sys.platform == "win32":
        # dshow addresses cameras by name -- needs the ffmpeg listing, which
        # is a blocking subprocess and therefore only run by
        # `refresh_camera_devices`, never inline.
        return []
    return sorted(glob.glob("/dev/video*"))


def list_camera_devices(cache: "dict[str, Any] | None" = None) -> list[str]:
    """Candidate device ids/names for `/photo <device>` completion.

    Never blocks: serves the cache when fresh, otherwise computes the cheap
    per-platform candidates (Termux/avfoundation numeric ids, /dev/video*
    globs). Windows dshow names need a subprocess probe -- they appear once
    `refresh_camera_devices` lands (kick it off with
    `maybe_refresh_camera_devices`). Returns an empty list when nothing can
    be offered yet.
    """
    if cache is None:
        cache = _default_device_cache
    cached = cache.get("devices")
    if (
        isinstance(cached, list)
        and time.monotonic() - cache.get("time", 0.0) < _DEVICE_CACHE_TTL_SECONDS
    ):
        return list(cached)

    devices = _compute_camera_devices_sync()
    cache["time"] = time.monotonic()
    cache["devices"] = devices
    return devices


async def refresh_camera_devices(cache: "dict[str, Any] | None" = None) -> list[str]:
    """Probe devices, including the blocking Windows ffmpeg listing.

    Awaiting this is safe from coroutines only; completion uses
    `maybe_refresh_camera_devices` to schedule it as a fire-and-forget task
    instead, so a slow probe never blocks a keystroke.
    """
    if cache is None:
        cache = _default_device_cache
    # lazy: tests patch zrb.config.helper.is_termux; hoisting would bind the
    # name at this module's load time and bypass the mock.
    from zrb.config.helper import is_termux

    if not is_termux() and sys.platform == "win32":
        devices = await _dshow_device_names()
    else:
        devices = _compute_camera_devices_sync()
    cache["time"] = time.monotonic()
    cache["devices"] = devices
    return devices


def maybe_refresh_camera_devices(cache: "dict[str, Any] | None" = None) -> None:
    """Schedule a device-probe refresh when the cache is stale.

    Fire-and-forget: the completer calls this synchronously on every `/photo`
    completion pass; the probe runs as a background task and the next
    completion pass picks up its result. No-op outside a running loop.
    """
    if cache is None:
        cache = _default_device_cache
    if cache.get("refreshing"):
        return
    if (
        isinstance(cache.get("devices"), list)
        and time.monotonic() - float(cache.get("time", 0.0)) < _DEVICE_CACHE_TTL_SECONDS
    ):
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _refresh() -> None:
        try:
            await refresh_camera_devices(cache)
        except Exception as e:
            logger.debug(f"Camera device refresh failed: {e}")
        finally:
            cache["refreshing"] = False

    cache["refreshing"] = True
    loop.create_task(_refresh())


CAPTURE_TIMEOUT_SECONDS = 15


async def _run(cmd: list[str]) -> bytes | None:
    global _last_ffmpeg_error
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=CAPTURE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            _last_ffmpeg_error = (
                f"capture timed out after {CAPTURE_TIMEOUT_SECONDS}s -- the "
                "camera opened but never delivered a frame (over WSL2 this "
                "usually means usbipd's USB/IP tunnel can't keep up with the "
                "requested format/resolution)"
            )
            return None
        if proc.returncode == 0 and stdout:
            _last_ffmpeg_error = None
            return stdout
        _last_ffmpeg_error = stderr.decode(errors="ignore").strip()[-500:]
        return None
    except FileNotFoundError:
        return None


def missing_tool_hint() -> str:
    """Return a short help string explaining why camera capture failed."""
    # lazy: tests patch zrb.config.helper.is_termux; hoisting would bind
    # the name at this module's load time and bypass the mock.
    from zrb.config.helper import is_termux

    if is_termux():
        hint = "  Install the Termux:API app (F-Droid) and `pkg install termux-api`.\n"
    elif sys.platform == "darwin":
        hint = (
            "  Install ffmpeg (brew install ffmpeg) and grant your terminal "
            "app camera access in System Settings > Privacy & Security > "
            "Camera.\n"
        )
    elif sys.platform == "win32":
        hint = (
            "  Install ffmpeg (https://ffmpeg.org) and make sure a webcam "
            "driver is installed. If detection fails, run `ffmpeg -f dshow "
            "-list_devices true -i dummy` to find your device name and pass "
            'it explicitly: /photo "<device name>".\n'
        )
    elif is_wsl():
        doc_url = (
            "https://github.com/state-alchemists/zrb/blob/main/docs/"
            "advanced-topics/llm-integration.md#troubleshooting-voice--photo"
        )
        if glob.glob("/dev/video*"):
            # The device node exists, so usbipd-win + the kernel driver are
            # both fine -- ffmpeg opened the camera but got no frame, which
            # on WSL2 is almost always usbipd-win's USB/IP tunnel failing to
            # sustain the video stream (not a zrb-side timeout tuning issue).
            hint = (
                "  Install ffmpeg if it's missing. /dev/video* exists, so the "
                "camera is attached and the driver is loaded -- ffmpeg just "
                "isn't getting a frame from it. WSL2's USB/IP tunnel "
                "(usbipd-win) often can't sustain a webcam stream even at "
                "reduced resolution/format; an external USB webcam is far "
                "more reliable than a laptop's integrated one over USB/IP. "
                f"Details: {doc_url}\n"
            )
        else:
            hint = (
                "  Install ffmpeg if it's missing. No /dev/video* device. "
                "Attaching the camera with usbipd-win "
                "(https://github.com/dorssel/usbipd-win) is necessary but not "
                "sufficient: the stock WSL2 kernel ships with no camera "
                "driver at all (no uvcvideo/v4l2), so usbipd can attach the "
                "USB device yet no /dev/video* node ever appears. Building a "
                "custom WSL2 kernel with USB Video Class support is required "
                f"-- step-by-step instructions: {doc_url}\n"
            )
    else:
        hint = (
            "  Install ffmpeg. If no camera is found, check /dev/video* "
            "permissions (add your user to the `video` group).\n"
        )
    if _last_ffmpeg_error:
        hint += f"  ffmpeg said: {_last_ffmpeg_error}\n"
    return hint

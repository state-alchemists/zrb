"""Camera capture through ffmpeg: avfoundation on macOS, dshow on Windows
(auto-detecting the first video device), v4l2 on Linux and WSL.

No Python dependency: capture shells out to ffmpeg.

WSL2 camera capture has two separate, layered failure modes -- see
`docs/llm/voice-photo-troubleshooting.md` for
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
   delivered. `FfmpegCameraBackend` works around this by requesting MJPEG
   (compressed on-camera) at 640x480 first -- tested as the largest size
   that lands reliably over USB/IP; 720p MJPEG still hangs, since this is an
   isochronous-transfer reliability ceiling, not simply a bandwidth budget.
   The capture timeout is the backstop for cameras/setups where even that
   still hangs.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import re
import shutil
import sys
import time
from typing import Any

from zrb.config.helper import is_wsl
from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend
from zrb.llm.camera.backend.deadline import (
    create_deadline,
    get_earlier,
    get_remaining,
)

logger = logging.getLogger(__name__)

DSHOW_LIST_TIMEOUT_SECONDS = 5
DEVICE_CACHE_TTL_SECONDS = 60
_TROUBLESHOOTING_URL = (
    "https://github.com/state-alchemists/zrb/blob/main/docs/"
    "llm/voice-photo-troubleshooting.md"
)


class FfmpegCameraBackend(AnyCameraBackend):
    """ffmpeg capture; a device is an avfoundation index, a dshow name, or a
    /dev/video* path. A capture taking over *timeout* seconds, all attempts
    together, is abandoned; ``0`` means no limit."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout
        self._last_error: str | None = None
        # {"time": float, "devices": list[str], "refreshing": bool}
        self._device_cache: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "ffmpeg"

    @property
    def last_error(self) -> str | None:
        """The tail of ffmpeg's error output from the last failed capture."""
        return self._last_error

    async def capture(self, device: str | None) -> bytes | None:
        return await self.capture_by(device, None)

    async def capture_by(
        self, device: str | None, deadline: float | None
    ) -> bytes | None:
        """`capture`, giving up at *deadline* (`time.monotonic()`) or after
        this backend's own timeout, whichever comes first."""
        deadline = get_earlier(deadline, create_deadline(self._timeout))
        try:
            return await self._capture(device, deadline)
        except Exception:
            return None

    async def _capture(
        self, device: str | None, deadline: float | None
    ) -> bytes | None:
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
            name = device or await self._get_dshow_default_device()
            if name is None:
                return None
            input_fmt, input_arg = "dshow", f"video={name}"
        else:
            input_fmt, input_arg = "v4l2", device or "/dev/video0"
            # Raw YUYV at max resolution hangs over WSL2's usbipd-win tunnel,
            # and so does 720p MJPEG; 640x480 MJPEG is the largest that lands.
            # Cameras without MJPEG fall back to the raw default.
            mjpeg_args = ["-input_format", "mjpeg", "-video_size", "640x480"]
            data = await self._run(
                _ffmpeg_cmd(input_fmt, mjpeg_args, input_arg), deadline
            )
            if data is not None:
                return data
        return await self._run(_ffmpeg_cmd(input_fmt, extra_args, input_arg), deadline)

    async def _run(self, cmd: list[str], deadline: float | None) -> bytes | None:
        timeout = get_remaining(deadline)
        if timeout == 0:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return None
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            self._last_error = (
                f"capture timed out after {self._timeout}s -- the camera opened "
                "but never delivered a frame (over WSL2 this usually means "
                "usbipd's USB/IP tunnel can't keep up with the requested "
                "format/resolution)"
            )
            return None
        if proc.returncode == 0 and stdout:
            self._last_error = None
            return stdout
        self._last_error = stderr.decode(errors="ignore").strip()[-500:]
        return None

    async def _get_dshow_default_device(self) -> str | None:
        names = await _list_dshow_devices()
        return names[0] if names else None

    def list_devices(self) -> list[str]:
        """Cached candidates, refreshed in the background when stale.

        Windows dshow names need a slow subprocess probe: they appear once the
        refresh started here has landed.
        """
        self.schedule_device_refresh()
        cache = self._device_cache
        cached = cache.get("devices")
        if isinstance(cached, list) and self._is_cache_fresh():
            return list(cached)
        devices = _list_devices_now()
        cache["time"] = time.monotonic()
        cache["devices"] = devices
        return devices

    async def refresh_devices(self) -> list[str]:
        """Probe devices, including the slow Windows ffmpeg listing."""
        if sys.platform == "win32":
            devices = await _list_dshow_devices()
        else:
            devices = _list_devices_now()
        self._device_cache["time"] = time.monotonic()
        self._device_cache["devices"] = devices
        return devices

    def schedule_device_refresh(self) -> "asyncio.Task[None] | None":
        """Start `refresh_devices` in the background when the cache is stale.

        Returns the task, or ``None`` when the cache is fresh, a refresh is
        already running, or there is no running loop.
        """
        cache = self._device_cache
        if cache.get("refreshing"):
            return None
        if isinstance(cache.get("devices"), list) and self._is_cache_fresh():
            return None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return None

        async def refresh() -> None:
            try:
                await self.refresh_devices()
            except Exception as e:
                logger.debug(f"Camera device refresh failed: {e}")
            finally:
                cache["refreshing"] = False

        cache["refreshing"] = True
        return loop.create_task(refresh())

    def _is_cache_fresh(self) -> bool:
        age = time.monotonic() - float(self._device_cache.get("time", 0.0))
        return age < DEVICE_CACHE_TTL_SECONDS

    def get_failure_hint(self) -> str:
        hint = _get_platform_hint()
        if self._last_error:
            hint += f"  ffmpeg said: {self._last_error}\n"
        return hint


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


async def _list_dshow_devices() -> list[str]:
    """All dshow video device names, via ffmpeg's device listing.

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
        try:
            _, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=DSHOW_LIST_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return []
    except FileNotFoundError:
        return []
    return re.findall(r'"([^"]+)"\s*\(video\)', stderr.decode(errors="ignore"))


def _list_devices_now() -> list[str]:
    """Cheap, non-blocking device candidates; empty where a probe is needed."""
    if sys.platform == "darwin":
        # avfoundation device index; probing requires a full ffmpeg listing.
        return ["0", "1"]
    if sys.platform == "win32":
        # dshow addresses cameras by name -- only the slow listing knows them.
        return []
    return sorted(glob.glob("/dev/video*"))


def _get_platform_hint() -> str:
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
    if is_wsl():
        return _get_wsl_hint()
    return (
        "  Install ffmpeg. If no camera is found, check /dev/video* "
        "permissions (add your user to the `video` group).\n"
    )


def _get_wsl_hint() -> str:
    if glob.glob("/dev/video*"):
        # The device node exists, so usbipd-win + the kernel driver are both
        # fine -- ffmpeg opened the camera but got no frame, which on WSL2 is
        # almost always usbipd-win's USB/IP tunnel failing to sustain the
        # video stream (not a zrb-side timeout tuning issue).
        return (
            "  Install ffmpeg if it's missing. /dev/video* exists, so the "
            "camera is attached and the driver is loaded -- ffmpeg just "
            "isn't getting a frame from it. WSL2's USB/IP tunnel "
            "(usbipd-win) often can't sustain a webcam stream even at "
            "reduced resolution/format; an external USB webcam is far "
            "more reliable than a laptop's integrated one over USB/IP. "
            f"Details: {_TROUBLESHOOTING_URL}\n"
        )
    return (
        "  Install ffmpeg if it's missing. No /dev/video* device. "
        "Attaching the camera with usbipd-win "
        "(https://github.com/dorssel/usbipd-win) is necessary but not "
        "sufficient: the stock WSL2 kernel ships with no camera "
        "driver at all (no uvcvideo/v4l2), so usbipd can attach the "
        "USB device yet no /dev/video* node ever appears. Building a "
        "custom WSL2 kernel with USB Video Class support is required "
        f"-- step-by-step instructions: {_TROUBLESHOOTING_URL}\n"
    )

"""Camera capture on Android via the Termux:API app.

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
import shutil
import uuid

from zrb.config.config import CFG
from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend
from zrb.llm.camera.backend.deadline import (
    communicate_within,
    create_deadline,
    get_earlier,
    get_remaining,
)

# Termux's real home directory is always at this fixed location, regardless
# of whether the caller is native Termux or a proot-distro guest.
TERMUX_HOME = "/data/data/com.termux/files/home"


class TermuxCameraBackend(AnyCameraBackend):
    """`termux-camera-photo`; a device is a camera id (``0`` back, ``1`` front).

    The app writes each photo to a fresh file in Termux's home, named for
    `CFG.ROOT_GROUP_NAME`, or to *photo_path*; the file is removed before and
    after, so a failed capture never returns an earlier photo. A capture taking
    over *timeout* seconds is abandoned; ``0`` means no limit.
    """

    def __init__(self, photo_path: str | None = None, timeout: float = 15.0) -> None:
        self._photo_path = photo_path
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "termux"

    @property
    def is_available(self) -> bool:
        return shutil.which("termux-camera-photo") is not None

    async def capture(self, device: str | None) -> bytes | None:
        return await self.capture_by(device, None)

    async def capture_by(
        self, device: str | None, deadline: float | None
    ) -> bytes | None:
        """`capture`, giving up at *deadline* (`time.monotonic()`) or after
        this backend's own timeout, whichever comes first."""
        deadline = get_earlier(deadline, create_deadline(self._timeout))
        path = self._photo_path or os.path.join(
            TERMUX_HOME, f".{CFG.ROOT_GROUP_NAME}_camera_{uuid.uuid4().hex}.jpg"
        )
        _remove(path)
        try:
            return await self._capture(device, path, deadline)
        finally:
            _remove(path)

    async def _capture(
        self, device: str | None, path: str, deadline: float | None
    ) -> bytes | None:
        timeout = get_remaining(deadline)
        if timeout == 0:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                "termux-camera-photo",
                "-c",
                device or "0",
                path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except Exception:
            return None
        try:
            await communicate_within(proc, timeout)
        except Exception:
            return None
        try:
            with open(path, "rb") as photo_file:
                return photo_file.read() or None
        except OSError:
            return None

    def list_devices(self) -> list[str]:
        return ["0", "1"]

    def get_failure_hint(self) -> str:
        return "  Install the Termux:API app (F-Droid) and `pkg install termux-api`.\n"


def _remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass

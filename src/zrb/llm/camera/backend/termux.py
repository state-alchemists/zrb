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

from zrb.config.config import CFG
from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend

# Termux's real home directory is always at this fixed location, regardless
# of whether the caller is native Termux or a proot-distro guest.
TERMUX_HOME = "/data/data/com.termux/files/home"


class TermuxCameraBackend(AnyCameraBackend):
    """`termux-camera-photo`; a device is a camera id (``0`` back, ``1`` front).

    The app writes the photo to *photo_path*, by default a dot-file named for
    `CFG.ROOT_GROUP_NAME` in Termux's home. A capture taking over *timeout*
    seconds is abandoned.
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
        path = self._photo_path or os.path.join(
            TERMUX_HOME, f".{CFG.ROOT_GROUP_NAME}_camera_photo.jpg"
        )
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
            await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return None
        except Exception:
            return None
        if not (os.path.exists(path) and os.path.getsize(path) > 0):
            return None
        with open(path, "rb") as photo_file:
            data = photo_file.read()
        try:
            os.unlink(path)
        except OSError:
            pass
        return data

    def list_devices(self) -> list[str]:
        return ["0", "1"]

    def get_failure_hint(self) -> str:
        return "  Install the Termux:API app (F-Droid) and `pkg install termux-api`.\n"

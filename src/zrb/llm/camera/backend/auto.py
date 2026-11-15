from __future__ import annotations

import asyncio

from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend
from zrb.llm.camera.backend.ffmpeg import FfmpegCameraBackend
from zrb.llm.camera.backend.remote import RemoteCameraBackend
from zrb.llm.camera.backend.termux import TermuxCameraBackend
from zrb.llm.util.deadline import create_deadline, get_remaining
from zrb.util.platform import is_termux


class AutoCameraBackend(AnyCameraBackend):
    """This machine's cameras: Termux:API on Android when installed, falling
    back to ffmpeg. Both attempts together take at most *timeout* seconds;
    ``0`` means no limit.

    *remote* is the page's cameras, when there is a page at all. A name this
    machine does not have is looked for there, so `phone-back` reaches the phone
    and `0` still reaches the laptop; a name the page does not answer leaves no
    photo rather than the local camera's, which is the rule the rest of this
    package keeps — a named camera does not become another camera's picture.
    Nothing is asked of a page for a capture that names no device: the default
    is this machine's, as it always was.

    A name is only called absent once this machine's list has settled: the slow
    platform listings land behind the fast one, so a camera that is about to
    appear must not be handed to the page in the meantime.
    """

    def __init__(
        self,
        termux: TermuxCameraBackend | None = None,
        ffmpeg: FfmpegCameraBackend | None = None,
        timeout: float = 15.0,
        remote: RemoteCameraBackend | None = None,
    ) -> None:
        self._termux = termux or TermuxCameraBackend()
        self._ffmpeg = ffmpeg or FfmpegCameraBackend()
        self._timeout = timeout
        self._remote = remote

    @property
    def name(self) -> str:
        return "auto"

    async def capture(self, device: str | None) -> bytes | None:
        deadline = create_deadline(self._timeout)
        page = await self._page_holding(device, deadline)
        if page is not None:
            return await page.capture_by(device, deadline)
        if is_termux() and self._termux.is_available:
            data = await self._termux.capture_by(device, deadline)
            if data is not None:
                return data
        return await self._ffmpeg.capture_by(device, deadline)

    def list_devices(self) -> list[str]:
        local = self._local_device_names()
        if self._remote is None:
            return local
        # The page's own, after this machine's: a name both answer to stays the
        # local camera's, since that is what it meant before a page existed.
        page = self._remote.list_devices()
        return local + [name for name in page if name not in local]

    def get_failure_hint(self) -> str:
        if self._remote is not None and self._remote.last_error:
            # The name went to the page, so its refusal is the one that matters.
            return self._remote.get_failure_hint()
        return self._local_hint()

    def _local(self) -> AnyCameraBackend:
        return self._termux if is_termux() else self._ffmpeg

    def _local_device_names(self) -> list[str]:
        return self._local().list_devices()

    async def _page_holding(
        self, device: str | None, deadline: float | None
    ) -> RemoteCameraBackend | None:
        """The page, when *device* is a name this machine does not have.

        Absence is only believed once the list has settled. On Windows the names
        come from a slow ffmpeg probe that lands behind the fast list, so the
        first `list_devices` after a cold cache lacks the very camera about to be
        asked for — and a name that is merely not counted yet must not become the
        page's photo.
        """
        if self._remote is None or not device:
            return None
        if device in self._local_device_names():
            return None
        if device in await self._settled_device_names(deadline):
            return None
        return self._remote

    async def _settled_device_names(self, deadline: float | None) -> list[str]:
        """This machine's names once its slow listing has landed; the names it had
        if that could not finish in time."""
        try:
            return await asyncio.wait_for(
                self._local().refresh_devices(), timeout=get_remaining(deadline)
            )
        except (OSError, RuntimeError, ValueError, asyncio.TimeoutError):
            return self._local_device_names()

    def _local_hint(self) -> str:
        if not is_termux():
            return self._ffmpeg.get_failure_hint()
        hint = self._termux.get_failure_hint()
        if self._ffmpeg.last_error:
            hint += f"  ffmpeg said: {self._ffmpeg.last_error}\n"
        return hint

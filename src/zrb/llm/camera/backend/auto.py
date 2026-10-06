from __future__ import annotations

from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend
from zrb.llm.camera.backend.deadline import create_deadline
from zrb.llm.camera.backend.ffmpeg import FfmpegCameraBackend
from zrb.llm.camera.backend.termux import TermuxCameraBackend


class AutoCameraBackend(AnyCameraBackend):
    """Termux:API on Android when installed, falling back to ffmpeg. Both
    attempts together take at most *timeout* seconds; ``0`` means no limit."""

    def __init__(
        self,
        termux: TermuxCameraBackend | None = None,
        ffmpeg: FfmpegCameraBackend | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._termux = termux or TermuxCameraBackend()
        self._ffmpeg = ffmpeg or FfmpegCameraBackend()
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "auto"

    async def capture(self, device: str | None) -> bytes | None:
        deadline = create_deadline(self._timeout)
        if _is_termux() and self._termux.is_available:
            data = await self._termux.capture_by(device, deadline)
            if data is not None:
                return data
        return await self._ffmpeg.capture_by(device, deadline)

    def list_devices(self) -> list[str]:
        if _is_termux():
            return self._termux.list_devices()
        return self._ffmpeg.list_devices()

    def get_failure_hint(self) -> str:
        if not _is_termux():
            return self._ffmpeg.get_failure_hint()
        hint = self._termux.get_failure_hint()
        if self._ffmpeg.last_error:
            hint += f"  ffmpeg said: {self._ffmpeg.last_error}\n"
        return hint


def _is_termux() -> bool:
    # lazy: tests patch zrb.config.helper.is_termux; hoisting bypasses the mock
    from zrb.config.helper import is_termux

    return is_termux()

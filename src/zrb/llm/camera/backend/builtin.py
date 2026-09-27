from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend
from zrb.llm.camera.backend.auto import AutoCameraBackend
from zrb.llm.camera.backend.ffmpeg import FfmpegCameraBackend
from zrb.llm.camera.backend.termux import TermuxCameraBackend

if TYPE_CHECKING:
    from zrb.llm.camera.config import CameraConfig


def get_camera_backend(
    backend: "str | AnyCameraBackend", config: "CameraConfig"
) -> AnyCameraBackend:
    """*backend* itself, or the built-in one it names, built from the resolved
    *config*: ``auto`` (Termux:API when available, else ffmpeg), ``termux``
    or ``ffmpeg``."""
    if isinstance(backend, AnyCameraBackend):
        return backend
    name = backend.strip().lower() or "auto"
    timeout = config.timeout or 15.0
    if name == "auto":
        return AutoCameraBackend(
            termux=TermuxCameraBackend(timeout=timeout),
            ffmpeg=FfmpegCameraBackend(timeout),
        )
    if name == "termux":
        return TermuxCameraBackend(timeout=timeout)
    if name == "ffmpeg":
        return FfmpegCameraBackend(timeout)
    raise ValueError(
        f"unknown camera backend {backend!r}: use auto, termux, ffmpeg, "
        "or an AnyCameraBackend"
    )

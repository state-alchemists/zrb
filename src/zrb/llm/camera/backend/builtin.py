from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.camera.backend.any_camera_backend import AnyCameraBackend
from zrb.llm.camera.backend.auto import AutoCameraBackend
from zrb.llm.camera.backend.ffmpeg import FfmpegCameraBackend
from zrb.llm.camera.backend.remote import RemoteCameraBackend
from zrb.llm.camera.backend.termux import TermuxCameraBackend
from zrb.llm.contracts.util.face_server import get_remote_headers, get_remote_url

if TYPE_CHECKING:
    from zrb.llm.camera.config import CameraConfig


def get_camera_backend(
    backend: "str | AnyCameraBackend", config: "CameraConfig"
) -> AnyCameraBackend:
    """*backend* itself, or the built-in one it names, built from the resolved
    *config*: ``auto`` (Termux:API when available, else ffmpeg, and the page's
    cameras when a face server is configured), ``termux``, ``ffmpeg`` or
    ``remote`` (that page, on its own)."""
    if isinstance(backend, AnyCameraBackend):
        return backend
    name = backend.strip().lower() or "auto"
    timeout = config.timeout or 0.0
    if name == "auto":
        return AutoCameraBackend(
            termux=TermuxCameraBackend(timeout=timeout),
            ffmpeg=FfmpegCameraBackend(timeout),
            timeout=timeout,
            remote=_get_page_backend(timeout),
        )
    if name == "termux":
        return TermuxCameraBackend(timeout=timeout)
    if name == "ffmpeg":
        return FfmpegCameraBackend(timeout)
    if name == "remote":
        page = _get_page_backend(timeout)
        if page is None:
            raise ValueError(
                "the remote camera backend needs a face server: set "
                f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL to the page that holds "
                "the camera"
            )
        return page
    raise ValueError(
        f"unknown camera backend {backend!r}: use auto, termux, ffmpeg, "
        "remote, or an AnyCameraBackend"
    )


def _get_page_backend(timeout: float) -> RemoteCameraBackend | None:
    """The page's cameras, or ``None`` while zrb's own devices are the only ones."""
    url = get_remote_url()
    if url is None:
        return None
    return RemoteCameraBackend(url, headers=get_remote_headers(), timeout=timeout)

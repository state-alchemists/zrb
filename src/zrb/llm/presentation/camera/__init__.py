"""Camera capture for chat sessions: `enable_camera` adds `/photo [device]`."""

from zrb.llm.presentation.camera.backend import (
    AnyCameraBackend,
    AutoCameraBackend,
    FfmpegCameraBackend,
    RemoteCameraBackend,
    TermuxCameraBackend,
)
from zrb.llm.presentation.camera.config import CameraConfig
from zrb.llm.presentation.camera.feature import enable_camera

__all__ = [
    "AnyCameraBackend",
    "AutoCameraBackend",
    "CameraConfig",
    "FfmpegCameraBackend",
    "RemoteCameraBackend",
    "TermuxCameraBackend",
    "enable_camera",
]

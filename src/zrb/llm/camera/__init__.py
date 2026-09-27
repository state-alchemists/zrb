"""Camera capture for chat sessions: `enable_camera` adds `/photo [device]`."""

from zrb.llm.camera.backend import (
    AnyCameraBackend,
    AutoCameraBackend,
    FfmpegCameraBackend,
    TermuxCameraBackend,
)
from zrb.llm.camera.config import CameraConfig
from zrb.llm.camera.feature import enable_camera

__all__ = [
    "AnyCameraBackend",
    "AutoCameraBackend",
    "CameraConfig",
    "FfmpegCameraBackend",
    "TermuxCameraBackend",
    "enable_camera",
]

import pytest

from zrb.llm.camera import CameraConfig
from zrb.llm.camera.backend import (
    AutoCameraBackend,
    FfmpegCameraBackend,
    TermuxCameraBackend,
    get_camera_backend,
)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("auto", AutoCameraBackend),
        ("", AutoCameraBackend),
        (" FFmpeg ", FfmpegCameraBackend),
        ("termux", TermuxCameraBackend),
    ],
)
def test_names_map_to_builtin_backends(name, expected):
    backend = get_camera_backend(name, CameraConfig().resolve())
    assert isinstance(backend, expected)


def test_a_backend_object_is_used_as_is():
    backend = TermuxCameraBackend()
    assert get_camera_backend(backend, CameraConfig().resolve()) is backend


def test_an_unknown_name_is_refused():
    with pytest.raises(ValueError, match="unknown camera backend"):
        get_camera_backend("polaroid", CameraConfig().resolve())

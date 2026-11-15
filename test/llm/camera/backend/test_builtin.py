import pytest

from zrb.config.config import CFG
from zrb.llm.camera import CameraConfig
from zrb.llm.camera.backend import (
    AutoCameraBackend,
    FfmpegCameraBackend,
    RemoteCameraBackend,
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


def test_remote_without_a_face_server_is_refused(monkeypatch):
    """There is no page to ask: saying so beats a capture that waits for one."""
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", raising=False)

    with pytest.raises(ValueError, match="face server"):
        get_camera_backend("remote", CameraConfig().resolve())


def test_remote_is_the_page_the_voice_setting_names(monkeypatch):
    monkeypatch.setenv(
        f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", "http://127.0.0.1:7777/"
    )

    backend = get_camera_backend("remote", CameraConfig().resolve())

    assert isinstance(backend, RemoteCameraBackend)


def test_auto_carries_the_page_when_one_is_configured(monkeypatch):
    monkeypatch.setenv(
        f"{CFG.ENV_PREFIX}_LLM_VOICE_REMOTE_URL", "http://127.0.0.1:7777"
    )

    backend = get_camera_backend("auto", CameraConfig().resolve())

    assert isinstance(backend, AutoCameraBackend)

"""PillowScreenshotBackend: `ImageGrab` on Windows and X11, run in a killable
subprocess so a timed-out grab cannot tie up the shared asyncio executor."""

from __future__ import annotations

import asyncio
import io
import sys
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from zrb.llm.screenshot.backend import PillowScreenshotBackend


def _jpeg_bytes(size=(8, 6)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


class _FakeProcess:
    "Minimal async-process stand-in for `asyncio.create_subprocess_exec`."

    def __init__(self, stdout=b"", stderr=b"", returncode=0, hang_seconds=0):
        self._stdout = stdout
        self._stderr = stderr
        self._exit_code = returncode
        self._hang_seconds = hang_seconds
        self.returncode = None

    async def communicate(self):
        if self._hang_seconds:
            await asyncio.sleep(self._hang_seconds)
        self.returncode = self._exit_code
        return (self._stdout, self._stderr)

    def kill(self):
        self.returncode = -9

    async def wait(self):
        return self.returncode


def _spawning(stdout=b"", stderr=b"", returncode=0, hang_seconds=0, calls=None):
    "A subprocess stand-in that records argv, mirroring test_tool.py."

    def _make_proc(*args, **kwargs):
        if calls is not None:
            calls.append((list(args), kwargs))
        return _FakeProcess(stdout, stderr, returncode, hang_seconds)

    return patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=_make_proc),
    )


@pytest.mark.asyncio
async def test_windows_grabs_the_main_screen_as_jpeg(monkeypatch):
    calls: list = []
    monkeypatch.setattr("sys.platform", "win32")
    jpeg = _jpeg_bytes()
    with _spawning(stdout=jpeg, calls=calls):
        data = await PillowScreenshotBackend().capture(None)

    assert data == jpeg
    ((args, _),) = calls
    assert args[0] == sys.executable
    assert args[1] == "-c"
    assert args[3] == ""  # no display named


@pytest.mark.asyncio
async def test_windows_all_grabs_every_screen(monkeypatch):
    calls: list = []
    monkeypatch.setattr("sys.platform", "win32")
    jpeg = _jpeg_bytes()
    with _spawning(stdout=jpeg, calls=calls):
        await PillowScreenshotBackend().capture("all")

    ((args, _),) = calls
    assert args[3] == "all"


@pytest.mark.asyncio
async def test_x11_names_the_display_so_pillow_runs_no_program(monkeypatch):
    calls: list = []
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    jpeg = _jpeg_bytes()
    with _spawning(stdout=jpeg, calls=calls):
        await PillowScreenshotBackend().capture(None)
        await PillowScreenshotBackend().capture(":1")

    assert calls[0][0][3] == ""  # None becomes ""
    assert calls[1][0][3] == ":1"


@pytest.mark.asyncio
async def test_without_an_x_display_nothing_is_grabbed(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    backend = PillowScreenshotBackend()

    assert await backend.capture(None) is None
    assert "DISPLAY is unset" in backend.get_failure_hint()


@pytest.mark.asyncio
async def test_a_grab_error_is_reported(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    error = OSError("Pillow was built without XCB support")
    with _spawning(returncode=1, stderr=str(error).encode()):
        backend = PillowScreenshotBackend()
        assert await backend.capture(None) is None

    assert backend.last_error == str(error)
    assert backend.get_failure_hint().startswith("  pillow:")


@pytest.mark.asyncio
async def test_a_slow_grab_is_abandoned(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    backend = PillowScreenshotBackend(timeout=0.05)

    with _spawning(hang_seconds=0.3):
        assert await backend.capture(None) is None

    assert "timed out" in backend.last_error


@pytest.mark.asyncio
async def test_a_spent_deadline_grabs_nothing(monkeypatch):
    calls: list = []
    monkeypatch.setattr("PIL.ImageGrab.grab", lambda **kwargs: calls.append(kwargs))
    backend = PillowScreenshotBackend()

    assert await backend.capture_by(None, deadline=0.0) is None
    assert calls == []
    assert "no time left" in backend.last_error


def test_a_fresh_backend_has_no_hint():
    backend = PillowScreenshotBackend()
    assert backend.name == "pillow"
    assert backend.get_failure_hint() == ""

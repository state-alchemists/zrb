"`PillowScreenshotBackend`: `ImageGrab` on Windows and X11."

from __future__ import annotations

import io
import time

import pytest
from PIL import Image

from zrb.llm.screenshot.backend import PillowScreenshotBackend


def _grab_recorder(calls: list, image=None, error: Exception | None = None):
    def _grab(**kwargs):
        calls.append(kwargs)
        if error is not None:
            raise error
        return image or Image.new("RGBA", (8, 6))

    return _grab


@pytest.mark.asyncio
async def test_windows_grabs_the_main_screen_as_jpeg(monkeypatch):
    calls: list = []
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("PIL.ImageGrab.grab", _grab_recorder(calls))

    data = await PillowScreenshotBackend().capture(None)

    assert calls == [{"all_screens": False}]
    assert Image.open(io.BytesIO(data)).format == "JPEG"


@pytest.mark.asyncio
async def test_windows_all_grabs_every_screen(monkeypatch):
    calls: list = []
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("PIL.ImageGrab.grab", _grab_recorder(calls))

    await PillowScreenshotBackend().capture("all")

    assert calls == [{"all_screens": True}]


@pytest.mark.asyncio
async def test_x11_names_the_display_so_pillow_runs_no_program(monkeypatch):
    calls: list = []
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr("PIL.ImageGrab.grab", _grab_recorder(calls))

    await PillowScreenshotBackend().capture(None)
    await PillowScreenshotBackend().capture(":1")

    assert calls == [{"xdisplay": ":0"}, {"xdisplay": ":1"}]


@pytest.mark.asyncio
async def test_without_an_x_display_nothing_is_grabbed(monkeypatch):
    calls: list = []
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr("PIL.ImageGrab.grab", _grab_recorder(calls))
    backend = PillowScreenshotBackend()

    assert await backend.capture(None) is None
    assert calls == []
    assert "DISPLAY is unset" in backend.get_failure_hint()


@pytest.mark.asyncio
async def test_a_grab_error_is_reported(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    error = OSError("Pillow was built without XCB support")
    monkeypatch.setattr("PIL.ImageGrab.grab", _grab_recorder([], error=error))
    backend = PillowScreenshotBackend()

    assert await backend.capture(None) is None
    assert backend.last_error == "Pillow was built without XCB support"
    assert backend.get_failure_hint().startswith("  pillow:")


@pytest.mark.asyncio
async def test_a_slow_grab_is_abandoned(monkeypatch):
    def _slow_grab(**kwargs):
        time.sleep(0.3)
        return Image.new("RGB", (4, 4))

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("PIL.ImageGrab.grab", _slow_grab)
    backend = PillowScreenshotBackend(timeout=0.05)

    assert await backend.capture(None) is None
    assert "timed out" in backend.last_error


@pytest.mark.asyncio
async def test_a_spent_deadline_grabs_nothing(monkeypatch):
    calls: list = []
    monkeypatch.setattr("PIL.ImageGrab.grab", _grab_recorder(calls))
    backend = PillowScreenshotBackend()

    assert await backend.capture_by(None, deadline=0.0) is None
    assert calls == []
    assert "no time left" in backend.last_error


def test_a_fresh_backend_has_no_hint():
    backend = PillowScreenshotBackend()
    assert backend.name == "pillow"
    assert backend.get_failure_hint() == ""

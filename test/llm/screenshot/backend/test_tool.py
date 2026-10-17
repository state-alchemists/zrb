"`ScreenshotToolBackend`: one capture program, its arguments and its errors."

from __future__ import annotations

import asyncio
import base64
import os
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.screenshot.backend import SCREENSHOT_TOOLS, ScreenshotToolBackend


class _FakeProcess:
    "Minimal async-process stand-in for `asyncio.create_subprocess_exec`."

    def __init__(
        self,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        hang_seconds: float = 0,
    ):
        self._stdout = stdout
        self._stderr = stderr
        self._exit_code = returncode
        self._hang_seconds = hang_seconds
        self.returncode: int | None = None

    async def communicate(self):
        if self._hang_seconds:
            await asyncio.sleep(self._hang_seconds)
        self.returncode = self._exit_code
        return (self._stdout, self._stderr)

    def kill(self):
        self.returncode = -9

    async def wait(self):
        return self.returncode


@pytest.fixture
def every_tool_installed(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")


def _writing(payload: bytes, calls: list):
    "A subprocess stand-in that writes *payload* to the last argument."

    def _make_proc(*args, **kwargs):
        calls.append((list(args), kwargs))
        with open(args[-1], "wb") as image_file:
            image_file.write(payload)
        return _FakeProcess()

    return AsyncMock(side_effect=_make_proc)


def _backend(name: str, timeout: float = 15.0) -> ScreenshotToolBackend:
    return ScreenshotToolBackend(SCREENSHOT_TOOLS[name], timeout)


@pytest.mark.asyncio
async def test_screencapture_is_silent_and_takes_a_display_number(
    every_tool_installed,
):
    calls: list = []
    with patch("asyncio.create_subprocess_exec", new=_writing(b"jpeg", calls)):
        result = await _backend("screencapture").capture("2")

    assert result == b"jpeg"
    ((args, _),) = calls
    assert args[:6] == ["screencapture", "-x", "-t", "jpg", "-D", "2"]


@pytest.mark.asyncio
async def test_the_capture_file_is_gone_afterwards(every_tool_installed):
    calls: list = []
    with patch("asyncio.create_subprocess_exec", new=_writing(b"jpeg", calls)):
        await _backend("grim").capture(None)

    ((args, _),) = calls
    assert args[:3] == ["grim", "-t", "jpeg"]
    assert not os.path.exists(os.path.dirname(args[-1]))


@pytest.mark.asyncio
async def test_grim_takes_an_output_name(every_tool_installed):
    calls: list = []
    with patch("asyncio.create_subprocess_exec", new=_writing(b"jpeg", calls)):
        await _backend("grim").capture("eDP-1")

    ((args, _),) = calls
    assert args[3:5] == ["-o", "eDP-1"]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("gnome-screenshot", ["gnome-screenshot", "-f"]),
        ("spectacle", ["spectacle", "-b", "-n", "-f", "-o"]),
        ("scrot", ["scrot"]),
        ("import", ["import", "-window", "root"]),
    ],
)
@pytest.mark.asyncio
async def test_each_program_writes_the_capture_file(
    every_tool_installed, name, expected
):
    calls: list = []
    with patch("asyncio.create_subprocess_exec", new=_writing(b"img", calls)):
        result = await _backend(name).capture(None)

    assert result == b"img"
    ((args, kwargs),) = calls
    assert args[:-1] == expected
    assert kwargs["env"] is None


@pytest.mark.asyncio
async def test_an_x11_program_is_pointed_at_the_named_display(every_tool_installed):
    calls: list = []
    with patch("asyncio.create_subprocess_exec", new=_writing(b"img", calls)):
        await _backend("scrot").capture(":1")

    ((_, kwargs),) = calls
    assert kwargs["env"]["DISPLAY"] == ":1"


@pytest.mark.parametrize(
    "display, bounds",
    [(None, "PrimaryScreen.Bounds"), ("all", "VirtualScreen")],
)
@pytest.mark.asyncio
async def test_powershell_prints_the_screen_as_base64(
    every_tool_installed, display, bounds
):
    seen: list = []

    def _make_proc(*args, **kwargs):
        seen.append(list(args))
        return _FakeProcess(stdout=base64.b64encode(b"jpeg") + b"\r\n")

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await _backend("powershell.exe").capture(display)

    assert result == b"jpeg"
    assert seen[0][:4] == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
    ]
    assert bounds in seen[0][-1]


@pytest.mark.asyncio
async def test_powershell_output_that_is_not_base64_fails(every_tool_installed):
    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=b"Access denied!")),
    ):
        backend = _backend("powershell")
        result = await backend.capture(None)

    assert result is None
    assert "not a base64 image" in backend.get_failure_hint()


@pytest.mark.asyncio
async def test_a_failing_powershell_is_reported(every_tool_installed):
    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(returncode=1)),
    ):
        backend = _backend("powershell")
        result = await backend.capture(None)

    assert result is None
    assert "exited with code 1" in backend.get_failure_hint()


@pytest.mark.asyncio
async def test_a_missing_program_is_named(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    backend = _backend("grim")

    assert await backend.capture(None) is None
    assert backend.get_failure_hint() == "  grim: `grim` is not installed\n"


@pytest.mark.asyncio
async def test_the_program_error_is_passed_on(every_tool_installed):
    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(
            return_value=_FakeProcess(
                stderr=b"could not create image from display\n", returncode=1
            )
        ),
    ):
        backend = _backend("screencapture")
        result = await backend.capture(None)

    assert result is None
    assert "could not create image from display" in backend.last_error


@pytest.mark.asyncio
async def test_a_program_that_writes_nothing_fails(every_tool_installed):
    with patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=_FakeProcess())
    ):
        backend = _backend("scrot")
        result = await backend.capture(None)

    assert result is None
    assert backend.last_error == "exited without writing an image"


@pytest.mark.asyncio
async def test_a_program_that_cannot_start_fails(every_tool_installed):
    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=PermissionError("permission denied")),
    ):
        backend = _backend("import")
        result = await backend.capture(None)

    assert result is None
    assert "permission denied" in backend.get_failure_hint()


@pytest.mark.asyncio
async def test_a_hanging_program_is_abandoned(every_tool_installed):
    proc = _FakeProcess(hang_seconds=5)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        backend = _backend("grim", timeout=0.05)
        result = await backend.capture(None)

    assert result is None
    assert "timed out" in backend.last_error
    assert proc.returncode == -9


@pytest.mark.asyncio
async def test_a_spent_deadline_runs_nothing(every_tool_installed):
    spawn = AsyncMock()
    with patch("asyncio.create_subprocess_exec", new=spawn):
        backend = _backend("grim")
        result = await backend.capture_by(None, deadline=0.0)

    assert result is None
    spawn.assert_not_called()
    assert "no time left" in backend.last_error


def test_a_successful_backend_has_no_hint():
    assert _backend("grim").get_failure_hint() == ""
    assert _backend("grim").name == "grim"

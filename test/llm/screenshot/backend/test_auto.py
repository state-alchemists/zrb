"""AutoScreenshotBackend: the capture chain and failure hint per platform.

Pillow now runs in a subprocess (`sys.executable -c`), so the subprocess mock
records a Pillow attempt by its argv rather than by patching `PIL.ImageGrab`
in-process."""

from __future__ import annotations

import base64
import io
import sys
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from zrb.llm.screenshot.backend import AutoScreenshotBackend


def _jpeg_bytes(size=(8, 6)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


class _FakeProcess:
    def __init__(self, stdout: bytes = b"", stderr: bytes = b"", returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self._exit_code = returncode
        self.returncode: int | None = None

    async def communicate(self):
        self.returncode = self._exit_code
        return (self._stdout, self._stderr)

    def kill(self):
        self.returncode = -9

    async def wait(self):
        return self.returncode


def _is_pillow_proc(args: tuple) -> bool:
    return len(args) > 1 and args[0] == sys.executable and args[1] == "-c"


@pytest.fixture
def platform(monkeypatch):
    "A Linux desktop with no session; each test sets up its own."
    for var in ("WSL_DISTRO_NAME", "WSLENV", "WAYLAND_DISPLAY", "DISPLAY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("zrb.config.helper.is_termux", lambda: False)
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    return monkeypatch


def _programs(
    ran: list[str],
    working: set[str],
    *,
    pillow_ok: bool = True,
):
    """Run each program, recording it; only those in *working* write an image.
    Pillow's subprocess is recognised by its argv and succeeds unless
    *pillow_ok* is false."""

    def _make_proc(*args, **kwargs):
        if _is_pillow_proc(args):
            ran.append("pillow")
            if not pillow_ok:
                return _FakeProcess(stderr=b"cannot grab", returncode=1)
            return _FakeProcess(stdout=_jpeg_bytes())
        ran.append(args[0])
        if args[0] not in working:
            return _FakeProcess(stderr=b"no luck", returncode=1)
        if args[0].startswith("powershell"):
            return _FakeProcess(stdout=base64.b64encode(b"shot"))
        with open(args[-1], "wb") as image_file:
            image_file.write(b"shot")
        return _FakeProcess()

    return AsyncMock(side_effect=_make_proc)


async def _capture(
    working: set[str], *, pillow_ok: bool = True
) -> tuple[bytes | None, list[str], str]:
    ran: list[str] = []
    backend = AutoScreenshotBackend()
    with patch(
        "asyncio.create_subprocess_exec",
        new=_programs(ran, working, pillow_ok=pillow_ok),
    ):
        data = await backend.capture(None)
    return data, ran, backend.get_failure_hint()


@pytest.mark.asyncio
async def test_macos_uses_screencapture(platform):
    platform.setattr("sys.platform", "darwin")

    data, ran, _ = await _capture({"screencapture"})

    assert (data, ran) == (b"shot", ["screencapture"])


@pytest.mark.asyncio
async def test_macos_failure_points_at_screen_recording_permission(platform):
    platform.setattr("sys.platform", "darwin")

    data, _, hint = await _capture(set())

    assert data is None
    assert "Screen Recording" in hint
    assert "screencapture: no luck" in hint


@pytest.mark.asyncio
async def test_windows_uses_pillow_first(platform):
    platform.setattr("sys.platform", "win32")

    data, ran, _ = await _capture(set(), pillow_ok=True)

    assert data is not None
    assert ran == ["pillow"]


@pytest.mark.asyncio
async def test_windows_falls_back_to_powershell(platform):
    platform.setattr("sys.platform", "win32")

    data, ran, _ = await _capture({"powershell"}, pillow_ok=False)

    assert (data, ran) == (b"shot", ["pillow", "powershell"])


@pytest.mark.asyncio
async def test_windows_failure_lists_both_attempts(platform):
    platform.setattr("sys.platform", "win32")

    _, _, hint = await _capture(set(), pillow_ok=False)

    assert "interactive desktop" in hint
    assert "pillow: cannot grab" in hint
    assert "powershell: no luck" in hint


@pytest.mark.asyncio
async def test_wsl_captures_the_windows_desktop(platform):
    platform.setenv("WSL_DISTRO_NAME", "Ubuntu")
    platform.setenv("DISPLAY", ":0")

    data, ran, _ = await _capture({"powershell.exe"})

    assert (data, ran) == (b"shot", ["powershell.exe"])


@pytest.mark.asyncio
async def test_wsl_failure_explains_interop(platform):
    platform.setenv("WSL_DISTRO_NAME", "Ubuntu")

    _, _, hint = await _capture(set())

    assert "powershell.exe" in hint
    assert "interop" in hint


@pytest.mark.asyncio
async def test_wayland_tries_grim_then_the_desktop_tools(platform):
    platform.setenv("WAYLAND_DISPLAY", "wayland-0")
    platform.setenv("DISPLAY", ":0")

    data, ran, _ = await _capture({"spectacle"})

    assert data == b"shot"
    assert ran == ["grim", "gnome-screenshot", "spectacle"]


@pytest.mark.asyncio
async def test_wayland_never_falls_back_to_x11_grabbers(platform):
    platform.setenv("XDG_SESSION_TYPE", "wayland")
    platform.setenv("DISPLAY", ":0")

    data, ran, hint = await _capture(set())

    assert data is None
    assert ran == ["grim", "gnome-screenshot", "spectacle"]
    assert "Install grim" in hint


@pytest.mark.asyncio
async def test_x11_tries_pillow_then_the_programs(platform):
    platform.setenv("DISPLAY", ":0")

    data, ran, _ = await _capture({"import"}, pillow_ok=False)

    assert data == b"shot"
    assert ran == ["pillow", "scrot", "import"]


@pytest.mark.asyncio
async def test_x11_failure_suggests_a_program(platform):
    platform.setenv("DISPLAY", ":0")

    _, ran, hint = await _capture(set(), pillow_ok=False)

    assert ran == ["pillow", "scrot", "import", "gnome-screenshot", "spectacle"]
    assert "Install scrot" in hint


@pytest.mark.asyncio
async def test_without_a_graphical_session_nothing_runs(platform):
    data, ran, hint = await _capture(set())

    assert (data, ran) == (None, [])
    assert "No graphical session" in hint


@pytest.mark.asyncio
async def test_termux_cannot_capture_and_says_so(platform):
    platform.setattr("zrb.config.helper.is_termux", lambda: True)
    platform.setenv("DISPLAY", ":0")

    data, ran, hint = await _capture({"scrot"})

    assert (data, ran) == (None, [])
    assert "/attach" in hint


@pytest.mark.parametrize(
    "setup, displays",
    [
        ({"sys.platform": "darwin"}, ["1", "2"]),
        ({"sys.platform": "win32"}, ["all"]),
        ({"env": "WSL_DISTRO_NAME"}, ["all"]),
        ({}, []),
        ({"termux": True}, []),
    ],
)
def test_display_completion_per_platform(platform, setup, displays):
    if "sys.platform" in setup:
        platform.setattr("sys.platform", setup["sys.platform"])
    if "env" in setup:
        platform.setenv(setup["env"], "Ubuntu")
    if setup.get("termux"):
        platform.setattr("zrb.config.helper.is_termux", lambda: True)

    assert AutoScreenshotBackend().list_displays() == displays


def test_the_auto_backend_is_named_auto():
    assert AutoScreenshotBackend().name == "auto"

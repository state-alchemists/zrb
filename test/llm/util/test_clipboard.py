"""Public-API tests for clipboard image reading.

All paths exercise `get_clipboard_image()` and `missing_tool_hint()`.
Per AGENTS.md, no underscore-prefixed helpers are touched directly.
External dependencies (Pillow, osascript, powershell.exe, wl-paste,
xclip, the live filesystem) are mocked.
"""

from __future__ import annotations

import builtins
import io
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.util.clipboard import copy_text, get_clipboard_image, missing_tool_hint

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_env(monkeypatch):
    """Strip every clipboard-relevant env var before each test."""
    for var in ("WSL_DISTRO_NAME", "WSLENV", "WAYLAND_DISPLAY", "DISPLAY"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    return buf.getvalue()


def _bmp_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "green").save(buf, format="BMP")
    return buf.getvalue()


class _FakeProcess:
    """Minimal async-process stand-in for `asyncio.create_subprocess_exec`."""

    def __init__(self, stdout: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self.returncode = returncode

    async def communicate(self):
        return (self._stdout, b"")


def _block_pil_import(monkeypatch):
    """Make `from PIL import ...` raise ImportError for the test scope."""
    real_import = builtins.__import__

    def fail_pil(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("Pillow disabled for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_pil)


# ---------------------------------------------------------------------------
# get_clipboard_image — macOS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_macos_returns_png_when_pillow_finds_image(clean_env):
    from PIL import Image

    fake_img = Image.new("RGB", (8, 8), "blue")
    clean_env.setattr("sys.platform", "darwin")
    with patch("PIL.ImageGrab.grabclipboard", return_value=fake_img):

        result = await get_clipboard_image()

    assert isinstance(result, bytes)
    assert result.startswith(b"\x89PNG\r\n\x1a\n")  # PNG magic header


@pytest.mark.asyncio
async def test_macos_returns_none_when_clipboard_empty(clean_env):
    clean_env.setattr("sys.platform", "darwin")
    with patch("PIL.ImageGrab.grabclipboard", return_value=None):

        result = await get_clipboard_image()

    assert result is None


@pytest.mark.asyncio
async def test_macos_falls_back_to_osascript_when_pillow_missing(clean_env, tmp_path):
    """When Pillow is unavailable, osascript writes a tempfile we read back."""
    clean_env.setattr("sys.platform", "darwin")
    _block_pil_import(clean_env)

    payload = b"\x89PNG\r\n\x1a\nfake-png-bytes"
    written: dict = {}

    def _make_proc(*args, **kwargs):
        # The osascript invocation embeds the destination path inside the script
        # body; pull it out and write the payload there to mimic AppleScript.
        script = args[2] if len(args) > 2 else ""
        # crude but sufficient: the path lives between `POSIX file "` and `"`.
        marker = 'POSIX file "'
        start = script.find(marker) + len(marker)
        end = script.find('"', start)
        path = script[start:end]
        with open(path, "wb") as fh:
            fh.write(payload)
        written["path"] = path
        return _FakeProcess()

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        result = await get_clipboard_image()

    assert result == payload
    # Tempfile is cleaned up after read.
    assert not os.path.exists(written["path"])


@pytest.mark.asyncio
async def test_macos_osascript_returns_none_when_no_tempfile_written(clean_env):
    clean_env.setattr("sys.platform", "darwin")
    _block_pil_import(clean_env)

    with patch(
        "asyncio.create_subprocess_exec", new=AsyncMock(return_value=_FakeProcess())
    ):
        result = await get_clipboard_image()

    assert result is None


# ---------------------------------------------------------------------------
# get_clipboard_image — Windows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_windows_returns_png_when_pillow_finds_image(clean_env):
    from PIL import Image

    fake_img = Image.new("RGB", (4, 4), "white")
    clean_env.setattr("sys.platform", "win32")
    with patch("PIL.ImageGrab.grabclipboard", return_value=fake_img):

        result = await get_clipboard_image()

    assert isinstance(result, bytes)
    assert result.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_windows_returns_none_when_clipboard_empty(clean_env):
    clean_env.setattr("sys.platform", "win32")
    with patch("PIL.ImageGrab.grabclipboard", return_value=None):

        result = await get_clipboard_image()

    assert result is None


@pytest.mark.asyncio
async def test_windows_returns_none_when_pillow_missing(clean_env):
    clean_env.setattr("sys.platform", "win32")
    _block_pil_import(clean_env)

    result = await get_clipboard_image()

    assert result is None


# ---------------------------------------------------------------------------
# get_clipboard_image — Linux / WSL / Wayland / X11
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wsl_powershell_returns_png_bytes(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    payload = _png_bytes()

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=payload)),
    ):
        result = await get_clipboard_image()

    assert result == payload


@pytest.mark.asyncio
async def test_wslenv_alone_also_triggers_powershell_path(clean_env):
    """`WSLENV` set without `WSL_DISTRO_NAME` should still pick the WSL branch."""
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WSLENV", "TERM/u")
    payload = _png_bytes()

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=payload)),
    ):
        result = await get_clipboard_image()

    assert result == payload


@pytest.mark.asyncio
async def test_wsl_falls_through_when_powershell_yields_no_image(clean_env):
    """No image in PowerShell → does not return the empty stdout."""
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")
    # No WAYLAND_DISPLAY / DISPLAY set, so wl-paste/xclip subprocesses also
    # produce empty output. The whole chain should resolve to None.
    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=b"")),
    ):
        result = await get_clipboard_image()

    assert result is None


@pytest.mark.asyncio
async def test_wayland_png_path_returns_image(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WAYLAND_DISPLAY", "wayland-0")
    payload = _png_bytes()

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=payload)),
    ):
        result = await get_clipboard_image()

    assert result == payload


@pytest.mark.asyncio
async def test_wayland_bmp_is_reencoded_to_png(clean_env):
    """When wl-paste returns BMP, output should still be valid PNG bytes."""
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WAYLAND_DISPLAY", "wayland-0")
    bmp = _bmp_bytes()

    # All four wl-paste MIME-type queries hit the same FakeProcess; since we
    # return *the same* BMP for every type, the first attempt (image/png) hits
    # and the result enters the re-encode branch only when mime_type != PNG.
    # To force the re-encode branch deterministically, fail the PNG attempt
    # (returncode 1 → _run returns None) and succeed only on image/bmp.
    call_log: list[str] = []

    def _per_mime(*args, **kwargs):
        cmd = (
            list(args[0]) if args and isinstance(args[0], (list, tuple)) else list(args)
        )
        mime = cmd[cmd.index("--type") + 1] if "--type" in cmd else ""
        call_log.append(mime)
        if mime == "image/bmp":
            return _FakeProcess(stdout=bmp, returncode=0)
        return _FakeProcess(stdout=b"", returncode=1)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_per_mime)):
        result = await get_clipboard_image()

    assert isinstance(result, bytes)
    assert result.startswith(b"\x89PNG\r\n\x1a\n")
    assert "image/png" in call_log  # first attempt
    assert "image/bmp" in call_log  # second attempt that succeeded


@pytest.mark.asyncio
async def test_wayland_corrupt_non_png_returns_none(clean_env):
    """If the BMP bytes can't be decoded by Pillow, fall through to xclip."""
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WAYLAND_DISPLAY", "wayland-0")
    garbage = b"\x00\x01not-an-image"

    def _per_mime(*args, **kwargs):
        cmd = (
            list(args[0]) if args and isinstance(args[0], (list, tuple)) else list(args)
        )
        mime = cmd[cmd.index("--type") + 1] if "--type" in cmd else ""
        if mime == "image/bmp":
            return _FakeProcess(stdout=garbage, returncode=0)
        return _FakeProcess(stdout=b"", returncode=1)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_per_mime)):
        result = await get_clipboard_image()

    # Wayland branch yielded undecodable bytes; xclip fallback also has nothing.
    assert result is None


@pytest.mark.asyncio
async def test_macos_osascript_unlink_failure_does_not_propagate(clean_env, tmp_path):
    """If the post-read `os.unlink` fails, the data is still returned."""
    clean_env.setattr("sys.platform", "darwin")
    _block_pil_import(clean_env)

    payload = b"\x89PNG\r\n\x1a\nbytes"

    def _make_proc(*args, **kwargs):
        script = args[2] if len(args) > 2 else ""
        marker = 'POSIX file "'
        start = script.find(marker) + len(marker)
        end = script.find('"', start)
        path = script[start:end]
        with open(path, "wb") as fh:
            fh.write(payload)
        return _FakeProcess()

    real_unlink = os.unlink

    def flaky_unlink(p, *a, **kw):
        if "zrb_clipboard_img" in str(p):
            raise OSError("simulated race")
        return real_unlink(p, *a, **kw)

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=_make_proc)):
        with patch("zrb.llm.util.clipboard.os.unlink", side_effect=flaky_unlink):
            result = await get_clipboard_image()

    assert result == payload


@pytest.mark.asyncio
async def test_x11_xclip_returns_image(clean_env):
    clean_env.setattr("sys.platform", "linux")
    payload = _png_bytes()

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=payload)),
    ):
        result = await get_clipboard_image()

    assert result == payload


@pytest.mark.asyncio
async def test_linux_returns_none_when_xclip_yields_no_image(clean_env):
    clean_env.setattr("sys.platform", "linux")

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProcess(stdout=b"", returncode=1)),
    ):
        result = await get_clipboard_image()

    assert result is None


@pytest.mark.asyncio
async def test_subprocess_filenotfound_returns_none(clean_env):
    """If the binary is missing, `_run` swallows FileNotFoundError → None."""
    clean_env.setattr("sys.platform", "linux")

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=FileNotFoundError("xclip missing")),
    ):
        result = await get_clipboard_image()

    assert result is None


@pytest.mark.asyncio
async def test_unexpected_exception_is_swallowed(clean_env):
    """Top-level handler catches anything and returns None."""
    clean_env.setattr("sys.platform", "linux")

    with patch(
        "asyncio.create_subprocess_exec",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await get_clipboard_image()

    assert result is None


# ---------------------------------------------------------------------------
# missing_tool_hint
# ---------------------------------------------------------------------------


def test_missing_tool_hint_returns_empty_on_macos(clean_env):
    clean_env.setattr("sys.platform", "darwin")

    assert missing_tool_hint() == ""


def test_missing_tool_hint_returns_empty_on_windows(clean_env):
    clean_env.setattr("sys.platform", "win32")

    assert missing_tool_hint() == ""


def test_missing_tool_hint_returns_empty_inside_wsl(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WSL_DISTRO_NAME", "Ubuntu")

    assert missing_tool_hint() == ""


def test_missing_tool_hint_recommends_wl_clipboard_on_wayland_without_tool(
    clean_env,
):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WAYLAND_DISPLAY", "wayland-0")
    with patch("zrb.llm.util.clipboard.shutil.which", return_value=None):

        hint = missing_tool_hint()

    assert "wl-clipboard" in hint
    assert "wl-paste" in hint


def test_missing_tool_hint_silent_when_wayland_tool_present(clean_env):
    clean_env.setattr("sys.platform", "linux")
    clean_env.setenv("WAYLAND_DISPLAY", "wayland-0")
    with patch("zrb.llm.util.clipboard.shutil.which", return_value="/usr/bin/wl-paste"):

        assert missing_tool_hint() == ""


def test_missing_tool_hint_recommends_xclip_on_x11_without_tool(clean_env):
    clean_env.setattr("sys.platform", "linux")
    with patch("zrb.llm.util.clipboard.shutil.which", return_value=None):

        hint = missing_tool_hint()

    assert "xclip" in hint


def test_missing_tool_hint_silent_when_xclip_present(clean_env):
    clean_env.setattr("sys.platform", "linux")
    with patch("zrb.llm.util.clipboard.shutil.which", return_value="/usr/bin/xclip"):

        assert missing_tool_hint() == ""


# ---------------------------------------------------------------------------
# copy_text
# ---------------------------------------------------------------------------


def test_copy_text_success(clean_env):
    """copy_text returns True when pyperclip.copy succeeds."""
    fake_pyperclip = MagicMock()

    with patch.dict("sys.modules", {"pyperclip": fake_pyperclip}):
        result = copy_text("hello world")

    assert result is True
    fake_pyperclip.copy.assert_called_once_with("hello world")


def test_copy_text_falls_back_to_osc52(clean_env):
    """copy_text uses OSC 52 when pyperclip.copy fails and stdout is a tty."""
    mock_stdout = MagicMock()
    mock_stdout.isatty.return_value = True
    clean_env.setattr("sys.stdout", mock_stdout)

    mock_pyperclip = MagicMock()
    mock_pyperclip.copy.side_effect = Exception("clipboard unavailable")
    with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
        result = copy_text("hello")

    assert result is True
    # OSC 52 sequence written to stdout
    import base64
    encoded = base64.b64encode(b"hello").decode("ascii")
    written = "".join(c for c in mock_stdout.write.call_args[0][0] if c.isprintable())
    assert encoded in written


def test_copy_text_osc52_tmux_passthrough(clean_env):
    """OSC 52 is wrapped for tmux passthrough."""
    mock_stdout = MagicMock()
    mock_stdout.isatty.return_value = True
    clean_env.setattr("sys.stdout", mock_stdout)
    clean_env.setenv("TMUX", "/tmp/tmux-1000/default")

    mock_pyperclip = MagicMock()
    mock_pyperclip.copy.side_effect = Exception("clipboard unavailable")
    with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
        result = copy_text("test")

    assert result is True
    # Writes the tmux passthrough prefix
    assert "\x1bPtmux;\x1b\x1b]52;c;" in mock_stdout.write.call_args[0][0]


def test_copy_text_fails_when_no_tty_and_no_pyperclip(clean_env):
    """copy_text returns False when pyperclip fails and not a tty."""
    mock_stdout = MagicMock()
    mock_stdout.isatty.return_value = False
    clean_env.setattr("sys.stdout", mock_stdout)

    mock_pyperclip = MagicMock()
    mock_pyperclip.copy.side_effect = Exception("clipboard unavailable")
    with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
        result = copy_text("hello")

    assert result is False

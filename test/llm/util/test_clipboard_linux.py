"""Public-API tests for clipboard image reading.

All paths exercise `get_clipboard_image()` and `missing_tool_hint()`.
Per AGENTS.md, no underscore-prefixed helpers are touched directly.
External dependencies (Pillow, osascript, powershell.exe, wl-paste,
xclip, the live filesystem) are mocked.
"""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.util.clipboard import copy_text, get_clipboard_image, missing_tool_hint


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


class _FakeProcess:
    """Minimal async-process stand-in for `asyncio.create_subprocess_exec`."""

    def __init__(self, stdout: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self.returncode = returncode

    async def communicate(self):
        return (self._stdout, b"")


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


def test_copy_text_success(clean_env):
    """copy_text returns True when pyperclip.copy succeeds."""
    fake_pyperclip = MagicMock()

    with (
        patch.dict("sys.modules", {"pyperclip": fake_pyperclip}),
        patch("zrb.config.helper.is_termux", return_value=False),
    ):
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
    with (
        patch.dict("sys.modules", {"pyperclip": mock_pyperclip}),
        patch("zrb.config.helper.is_termux", return_value=False),
    ):
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
    with (
        patch.dict("sys.modules", {"pyperclip": mock_pyperclip}),
        patch("zrb.config.helper.is_termux", return_value=False),
    ):
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
    with (
        patch.dict("sys.modules", {"pyperclip": mock_pyperclip}),
        patch("zrb.config.helper.is_termux", return_value=False),
    ):
        result = copy_text("hello")

    assert result is False


def test_copy_text_termux_success(clean_env):
    """copy_text uses termux-clipboard-set on Termux when available."""
    import subprocess

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with (
        patch("zrb.config.helper.is_termux", return_value=True),
        patch(
            "zrb.llm.util.clipboard.subprocess.run", return_value=mock_proc
        ) as mock_run,
    ):
        result = copy_text("hello termux")

    assert result is True
    # Text goes over stdin, not argv: a large transcript would exceed ARG_MAX.
    mock_run.assert_called_once_with(
        ["termux-clipboard-set"],
        input=b"hello termux",
        timeout=3,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_copy_text_termux_fallback_to_pyperclip(clean_env):
    """copy_text falls back to pyperclip when termux-clipboard-set fails."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1  # termux-clipboard-set failed

    fake_pyperclip = MagicMock()

    with (
        patch("zrb.config.helper.is_termux", return_value=True),
        patch("zrb.llm.util.clipboard.subprocess.run", return_value=mock_proc),
        patch.dict("sys.modules", {"pyperclip": fake_pyperclip}),
    ):
        result = copy_text("hello")

    assert result is True
    fake_pyperclip.copy.assert_called_once_with("hello")

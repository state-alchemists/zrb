import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.base.commands import BaseUICommands


def test_handle_toggle_voice_still_blocked_without_vosk(ui):
    """No explicit opt-in and no vosk → the not-enabled warning stays."""
    env = {k: v for k, v in os.environ.items() if not k.endswith("_LLM_VOICE_ENABLED")}
    with patch.dict(os.environ, env, clear=True):
        with patch("zrb.llm.voice.engine.vosk_installed", return_value=False):
            result = ui.handle_toggle_voice("/voice")
    assert result is True
    assert ui.voice_mode_active is False
    assert any("not enabled" in o for o in ui.outputs)


def test_handle_toggle_voice_explicit_off_wins_over_vosk(ui):
    """`LLM_VOICE_ENABLED=false` disables voice even with vosk installed."""
    with patch.dict(os.environ, {"ZRB_LLM_VOICE_ENABLED": "false"}):
        with patch("zrb.llm.voice.engine.vosk_installed", return_value=True):
            result = ui.handle_toggle_voice("/voice")
    assert result is True
    assert ui.voice_mode_active is False
    assert any("not enabled" in o for o in ui.outputs)


def test_voice_command_in_help_text(ui):
    """Help text includes /voice when voice is enabled."""
    with patch.dict(os.environ, {"ZRB_LLM_VOICE_ENABLED": "true"}):
        help_text = ui.get_help_text()
        assert "/voice" in help_text


def test_voice_command_always_in_help(ui):
    """Help text always shows /voice regardless of voice enabled state."""
    with patch.dict(os.environ, {"ZRB_LLM_VOICE_ENABLED": "false"}):
        help_text = ui.get_help_text()
        assert "/voice" in help_text
    with patch.dict(os.environ, {"ZRB_LLM_VOICE_ENABLED": "true"}):
        help_text = ui.get_help_text()
        assert "/voice" in help_text


def test_classify_input_recognizes_voice(ui):
    """`/voice` is classified as a thinking_command."""
    with patch.dict(os.environ, {"ZRB_LLM_VOICE_ENABLED": "true"}):
        assert ui.classify_input("/voice") == "thinking_command"


def test_voice_handler_rejects_non_voice_input(ui):
    """`/q`, `/exit`, random text do NOT trigger the voice handler."""
    with patch.dict(os.environ, {"ZRB_LLM_VOICE_ENABLED": "true"}):
        assert ui.handle_toggle_voice("/q") is False
        assert ui.handle_toggle_voice("/exit") is False
        assert ui.handle_toggle_voice("hello") is False
        assert ui.handle_toggle_voice("/voice") is True


@pytest.mark.asyncio
async def test_shell_command_kills_process_when_cancelled_twice(ui):
    """A second cancel during teardown must not orphan the child process.

    Regression: the cleanup awaited `process.wait()` inside the CancelledError
    handler and caught only `Exception`. A cancel landing on that await (Ctrl+C
    again, or shutdown) is a `CancelledError` — a `BaseException` — so it skipped
    `process.kill()` entirely and left the process running.
    """
    killed = {"done": False}

    with patch("asyncio.create_subprocess_shell") as mock_sub:
        mock_proc = MagicMock()
        mock_proc.returncode = None
        # Streaming is cancelled, putting us in the CancelledError handler.
        mock_proc.stdout.readline = AsyncMock(side_effect=asyncio.CancelledError())
        mock_proc.stderr.readline = AsyncMock(return_value=b"")
        mock_proc.terminate = MagicMock()
        # The reaping await is itself cancelled — the second Ctrl+C.
        mock_proc.wait = AsyncMock(side_effect=asyncio.CancelledError())

        def _kill():
            killed["done"] = True

        mock_proc.kill = _kill
        mock_sub.return_value = mock_proc

        with pytest.raises(asyncio.CancelledError):
            await ui.run_shell_command("sleep 30")

    assert mock_proc.terminate.called
    assert killed["done"], "process was left running after a second cancel"


@pytest.mark.asyncio
async def test_shell_command_cleanup_survives_a_failing_ui_write(ui):
    """A UI write failure during teardown must not skip the process cleanup."""
    killed = {"done": False}
    real_append = ui.append_to_output

    def flaky_append(*args, **kwargs):
        if args and "[Cancelled]" in str(args[0]):
            raise RuntimeError("buffer gone during teardown")
        return real_append(*args, **kwargs)

    with patch("asyncio.create_subprocess_shell") as mock_sub:
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.stdout.readline = AsyncMock(side_effect=asyncio.CancelledError())
        mock_proc.stderr.readline = AsyncMock(return_value=b"")
        mock_proc.terminate = MagicMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.kill = lambda: killed.__setitem__("done", True)
        mock_sub.return_value = mock_proc

        ui.append_to_output = flaky_append
        try:
            with pytest.raises(RuntimeError):
                await ui.run_shell_command("sleep 30")
        finally:
            ui.append_to_output = real_append

    # terminate() ran before the UI write, so the child was reaped regardless.
    assert mock_proc.terminate.called

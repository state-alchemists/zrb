import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.ui.base.commands import BaseUICommands


class MockUI:
    """Stand-in for `BaseUI`: owns the state `BaseUICommands` and its
    conversation/model/exec collaborators read through `self._base_ui`,
    plus the `BaseUI` methods they call (`append_to_output`, `on_exit`, ...).
    Composes a real `BaseUICommands(self)` and forwards attribute
    lookups to it (and its sub-collaborators) so the many existing
    `ui.handle_*`/`ui.classify_input`/... call sites below keep working
    unchanged."""

    def __init__(self):
        self.exit_commands = ["/exit"]
        self.info_commands = ["/help"]
        self.save_commands = ["/save"]
        self.load_commands = ["/load"]
        self.rewind_commands = ["/rewind"]
        self.redirect_output_commands = ["/redirect"]
        self.attach_commands = ["/attach"]
        self.photo_commands = ["/photo"]
        self.yolo_toggle_commands = ["/yolo"]
        self.set_model_commands = ["/model"]
        self.exec_commands = ["/exec"]
        self.btw_commands = ["/btw"]
        self.plan_commands = ["/plan"]
        self.summarize_commands = ["/summarize"]
        self.copy_commands = []
        self.voice_commands = ["/voice"]
        self.voice_mode_active = False
        self.voice_recording_active = False
        self.voice_task = None
        self.voice_stop_event = None
        self.custom_commands = []

        self.execute_hook = MagicMock()
        self.execute_hook_blocking = AsyncMock(return_value=[])
        self.history_manager = MagicMock()
        self.replay_history = MagicMock()
        self.reset_session_token_usage = MagicMock()
        self.original_persona_snapshot = None
        self.active_subagent_persona = None
        self.snapshot_manager = MagicMock()
        self.message_queue = asyncio.Queue()
        self.pending_attachments = []
        self.is_thinking = False
        self.running_llm_task = None
        self.background_tasks = set()
        self.llm_task = MagicMock()
        self.llm_task.get_system_prompt.return_value = "mock system prompt"
        self.llm_task.llm_config.model = "mock-model"
        self.llm_task.llm_config.resolve_model.return_value = "mock-resolved-model"
        self.ctx = MagicMock()
        self.model = "test-model"
        self.conversation_session_name = "default"
        self.markdown_theme = None
        self.last_output = "some ai output"
        self.yolo = False
        self.plan_mode_active = False

        self.outputs = []
        self.exited = False

        self._cmds = BaseUICommands(self)

    def __getattr__(self, name):
        cmds = self.__dict__.get("_cmds")
        if cmds is None:
            raise AttributeError(name)
        for collaborator_attr in ("", "_conversation", "_models", "_exec"):
            holder = getattr(cmds, collaborator_attr) if collaborator_attr else cmds
            if hasattr(holder, name):
                return getattr(holder, name)
        raise AttributeError(name)

    def append_to_output(self, text, end="\n"):
        self.outputs.append(str(text) + end)

    def append_markdown(self, markdown_text):
        self.append_to_output(markdown_text)

    def invalidate_ui(self):
        pass

    def on_exit(self):
        self.exited = True

    async def update_system_info(self):
        pass

    def _get_output_field_width(self):
        return 80

    def submit_message(self, prompt):
        self.submitted_prompt = prompt


@pytest.fixture
def ui():
    return MockUI()


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

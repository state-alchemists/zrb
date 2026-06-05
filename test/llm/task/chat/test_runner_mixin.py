import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.task.chat.runner_mixin import RunnerMixin


class MockLLMChatTask(RunnerMixin):
    def __init__(self):
        self._uis = []
        self._ui_factories = []
        self._include_default_ui = True
        self._approval_channels = []
        self._yolo_xcom_key = "yolo"
        self._triggers = []
        self._response_handlers = []
        self._tool_policies = []
        self._argument_formatters = []
        self._markdown_theme = None
        self._custom_commands = []
        self._custom_model_names = []
        self._ui_greeting = "Hello"
        self._render_ui_greeting = False
        self._ui_assistant_name = "Zrb"
        self._render_ui_assistant_name = False
        self._ui_jargon = "Tasker"
        self._render_ui_jargon = False
        self._ui_ascii_art_name = "zrb"
        self._render_ui_ascii_art_name = False
        self._show_ollama_models = None
        self._show_pydantic_ai_models = None

    def _get_model(self, ctx):
        return "test-model"

    def _get_ui_conversation_name(self, ui, name):
        return name


@pytest.fixture
def runner():
    return MockLLMChatTask()


@pytest.mark.asyncio
async def test_run_non_interactive_session(runner):
    ctx = MagicMock()
    ctx.shared_print = MagicMock()
    ctx.xcom = {}

    llm_task_core = MagicMock()
    llm_task_core.async_run = AsyncMock(return_value="AI Output")

    res = await runner._run_non_interactive_session(
        ctx=ctx,
        llm_task_core=llm_task_core,
        initial_message="hi",
        initial_conversation_name="sess1",
        initial_yolo=False,
        initial_attachments=[],
    )

    assert res == "AI Output"
    assert ctx.xcom["__conversation_name__"] == "sess1"
    llm_task_core.async_run.assert_called_once()


# Simplified mock that doesn't inherit from BaseUI but implements the required protocol
class SimpleMockUI:
    def __init__(self, **kwargs):
        self.last_output = "Final"
        self.run_async = AsyncMock(return_value="Final")

    def append_to_output(self, *args, **kwargs):
        pass

    def set_approval_channel(self, chan):
        pass

    def set_tool_call_handler(self, handler):
        pass


@pytest.mark.asyncio
async def test_run_interactive_session_basic(runner):
    ctx = MagicMock()
    ctx.xcom = {}

    llm_task_core = MagicMock()
    history_manager = MagicMock()
    history_manager.load.return_value = []

    ui_commands = {
        k: []
        for k in [
            "summarize",
            "attach",
            "exit",
            "info",
            "save",
            "load",
            "rewind",
            "yolo_toggle",
            "set_model",
            "redirect_output",
            "exec",
            "btw",
            "plan",
            "build",
        ]
    }

    mock_ui = SimpleMockUI()

    with patch("zrb.llm.ui.default.ui.UI", return_value=mock_ui):
        res = await runner._run_interactive_session(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message=None,
            initial_conversation_name="sess1",
            initial_yolo=False,
            initial_attachments=[],
        )

        assert res == "Final"


@pytest.mark.asyncio
async def test_run_interactive_session_with_factories_and_multiplex(runner):
    runner._ui_factories = [lambda **kwargs: SimpleMockUI(**kwargs)]
    runner._include_default_ui = False
    runner._approval_channels = [MagicMock(), MagicMock()]

    ctx = MagicMock()
    ctx.xcom = {}
    llm_task_core = MagicMock()
    history_manager = MagicMock()

    ui_commands = {
        k: []
        for k in [
            "summarize",
            "attach",
            "exit",
            "info",
            "save",
            "load",
            "rewind",
            "yolo_toggle",
            "set_model",
            "redirect_output",
            "exec",
            "btw",
            "plan",
            "build",
        ]
    }

    mock_multi = MagicMock()
    mock_multi.run_async = AsyncMock(return_value="MultiResult")
    mock_multi.last_output = "MultiResult"

    with patch("zrb.llm.ui.multi_ui.MultiUI", return_value=mock_multi), patch(
        "zrb.llm.approval.multiplex_approval_channel.MultiplexApprovalChannel"
    ):
        res = await runner._run_interactive_session(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message=None,
            initial_conversation_name="sess1",
            initial_yolo=False,
            initial_attachments=[],
        )

        # When only one UI is resolved from factories, MultiUI is NOT used
        assert res == "Final"


def test_load_session_history_uses_replay_when_available(runner):
    """When a UI exposes replay_history, it must be used to render loaded history."""
    history_manager = MagicMock()
    history_manager.load.return_value = ["msg1", "msg2"]

    ui = MagicMock(spec=["replay_history", "append_to_output"])
    ui.replay_history = MagicMock()

    runner._load_session_history(ui, history_manager, "sess1")

    ui.replay_history.assert_called_once_with(["msg1", "msg2"])
    ui.append_to_output.assert_not_called()


def test_load_session_history_falls_back_to_text_dump(runner):
    """UIs without replay_history fall back to append_to_output with formatted text."""
    history_manager = MagicMock()
    history_manager.load.return_value = ["msg1"]

    class TextOnlyUI:
        def __init__(self):
            self.appended: list[str] = []

        def append_to_output(self, text):
            self.appended.append(text)

    ui = TextOnlyUI()

    with patch(
        "zrb.llm.util.history_formatter.format_history_as_text",
        return_value="FORMATTED",
    ):
        runner._load_session_history(ui, history_manager, "sess1")

    assert ui.appended == ["FORMATTED"]


def test_load_session_history_empty_name_is_noop(runner):
    """An empty conversation name must short-circuit the loader."""
    history_manager = MagicMock()
    ui = MagicMock(spec=["_replay_history", "append_to_output"])

    runner._load_session_history(ui, history_manager, "")

    history_manager.load.assert_not_called()
    ui._replay_history.assert_not_called()


def test_load_session_history_missing_file_is_silent(runner):
    """FileNotFoundError from the history manager must not surface to the user."""
    history_manager = MagicMock()
    history_manager.load.side_effect = FileNotFoundError("no such session")
    ui = MagicMock(spec=["_replay_history", "append_to_output"])

    # Should not raise
    runner._load_session_history(ui, history_manager, "sess-missing")

    ui._replay_history.assert_not_called()

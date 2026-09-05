from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.task.chat.running import ChatRunning
from zrb.llm.ui.ui_config import UIConfig


class MockLLMChatTask:
    """Stand-in for `LLMChatTask`: state `ChatRunning` reads plus the two
    methods (`get_model`, `get_ui_conversation_name`) implemented by the
    sibling `ChatExecution` collaborator on the real task facade."""

    def __init__(self):
        self.uis = []
        self.ui_factories = []
        self.include_default_ui = True
        self.approval_channels = []
        self.ui_config = UIConfig()
        self.triggers = []
        self.response_handlers = []
        self.tool_policies = []
        self.argument_formatters = []
        self.markdown_theme = None
        self.custom_commands = []
        self.custom_model_names = []
        self.ui_texts = {
            "greeting": ("Hello", False),
            "assistant_name": ("Zrb", False),
            "ascii_art": ("zrb", False),
            "jargon": ("Tasker", False),
        }

    def get_model(self, ctx):
        return "test-model"

    def get_ui_conversation_name(self, ui, name):
        return name


@pytest.fixture
def runner():
    return ChatRunning(MockLLMChatTask())


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


class FakeCustomCommand:
    """Duck-typed stand-in for AnyCustomCommand used to test slash-command
    resolution without depending on a concrete implementation."""

    def __init__(self, command: str, args: list[str], prompt_template: str):
        self.command = command
        self.description = "fake command"
        self.args = args
        self._prompt_template = prompt_template

    def get_prompt(self, kwargs: dict[str, str]) -> str:
        return self._prompt_template.format(**kwargs)


UI_COMMAND_KEYS = [
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
    "copy",
    "voice",
    "photo",
    "build",
]


@pytest.fixture
def ui_commands():
    return {k: [] for k in UI_COMMAND_KEYS}


def test_load_session_history_missing_file_is_silent(runner):
    """FileNotFoundError from the history manager must not surface to the user."""
    history_manager = MagicMock()
    history_manager.load.side_effect = FileNotFoundError("no such session")
    ui = MagicMock(spec=["replay_history", "append_to_output"])

    # Should not raise
    runner.load_session_history(ui, history_manager, "sess-missing")

    ui.replay_history.assert_not_called()


@pytest.mark.asyncio
async def test_run_interactive_session_applies_agent_mention_nudge(runner, ui_commands):
    """A plain message mentioning a known agent gets the nudge prepended
    before it reaches the UI."""
    ctx = MagicMock()
    ctx.xcom = {}

    llm_task_core = MagicMock()
    history_manager = MagicMock()
    history_manager.load.return_value = []

    mock_ui = SimpleMockUI()

    with (
        patch("zrb.llm.ui.default.ui.UI") as MockUI,
        patch(
            "zrb.llm.task.chat.running.resolve_agent_mention",
            return_value="NUDGED:hi @researcher",
        ) as mock_resolve_mention,
    ):
        MockUI.return_value = mock_ui

        res = await runner.run_interactive_session(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message="hi @researcher",
            initial_conversation_name="sess1",
            initial_yolo=False,
            initial_attachments=[],
        )

        assert res == "Final"
        mock_resolve_mention.assert_called_once_with("hi @researcher")
        assert MockUI.call_args.kwargs["initial_message"] == "NUDGED:hi @researcher"


@pytest.mark.asyncio
async def test_run_interactive_session_slash_command_skips_mention_resolution(
    runner, ui_commands
):
    """A resolved slash command must not also run through mention resolution --
    the two syntaxes are mutually exclusive."""
    runner.llm_chat_task.custom_commands = [
        FakeCustomCommand(
            command="/foo", args=["text"], prompt_template="RESOLVED:{text}"
        )
    ]

    ctx = MagicMock()
    ctx.xcom = {}

    llm_task_core = MagicMock()
    history_manager = MagicMock()
    history_manager.load.return_value = []

    mock_ui = SimpleMockUI()

    with (
        patch("zrb.llm.ui.default.ui.UI") as MockUI,
        patch(
            "zrb.llm.task.chat.running.resolve_agent_mention"
        ) as mock_resolve_mention,
    ):
        MockUI.return_value = mock_ui

        await runner.run_interactive_session(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message="/foo bar",
            initial_conversation_name="sess1",
            initial_yolo=False,
            initial_attachments=[],
        )

        mock_resolve_mention.assert_not_called()
        assert MockUI.call_args.kwargs["initial_message"] == "RESOLVED:bar"


@pytest.mark.asyncio
async def test_run_non_interactive_session_applies_agent_mention_nudge(runner):
    """Non-interactive (web) path applies the same mention nudge as the
    interactive path."""
    ctx = MagicMock()
    ctx.shared_print = MagicMock()
    ctx.xcom = {}

    llm_task_core = MagicMock()
    llm_task_core.async_run = AsyncMock(return_value="AI Output")

    with patch(
        "zrb.llm.task.chat.running.resolve_agent_mention",
        return_value="NUDGED:hi @researcher",
    ) as mock_resolve_mention:
        await runner.run_non_interactive_session(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=MagicMock(),
            ui_commands={},
            initial_message="hi @researcher",
            initial_conversation_name="sess1",
            initial_yolo=False,
            initial_attachments=[],
        )

    mock_resolve_mention.assert_called_once_with("hi @researcher")
    sent_session = llm_task_core.async_run.call_args.args[0]
    assert sent_session.shared_ctx.input["message"] == "NUDGED:hi @researcher"

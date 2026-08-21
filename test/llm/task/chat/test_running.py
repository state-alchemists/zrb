from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.task.chat.running import ChatRunning


class MockLLMChatTask:
    """Stand-in for `LLMChatTask`: state `ChatRunning` reads plus the two
    methods (`get_model`, `get_ui_conversation_name`) implemented by the
    sibling `ChatExecution` collaborator on the real task facade."""

    def __init__(self):
        self.uis = []
        self.ui_factories = []
        self.include_default_ui = True
        self.approval_channels = []
        self.yolo_xcom_key = "yolo"
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
        self.show_ollama_models = None
        self.show_pydantic_ai_models = None

    def get_model(self, ctx):
        return "test-model"

    def get_ui_conversation_name(self, ui, name):
        return name


@pytest.fixture
def runner():
    return ChatRunning(MockLLMChatTask())


@pytest.mark.asyncio
async def test_run_non_interactive_session(runner):
    ctx = MagicMock()
    ctx.shared_print = MagicMock()
    ctx.xcom = {}

    llm_task_core = MagicMock()
    llm_task_core.async_run = AsyncMock(return_value="AI Output")

    res = await runner.run_non_interactive_session(
        ctx=ctx,
        llm_task_core=llm_task_core,
        history_manager=MagicMock(),
        ui_commands={},
        initial_message="hi",
        initial_conversation_name="sess1",
        initial_yolo=False,
        initial_attachments=[],
    )

    assert res == "AI Output"
    assert ctx.xcom["__conversation_name__"] == "sess1"
    llm_task_core.async_run.assert_called_once()


@pytest.mark.asyncio
async def test_run_non_interactive_session_finalizes_attached_uis(runner):
    """A string result is handed to every attached UI's append_markdown --
    the only markdown-rendering pass the non-interactive (web) loop gets,
    since it never runs through the interactive _stream_ai_response."""
    ctx = MagicMock()
    ctx.shared_print = MagicMock()
    ctx.xcom = {}

    ui_with_markdown = MagicMock(spec=["append_markdown"])
    ui_without_markdown = MagicMock(spec=[])  # e.g. a UI with no rich rendering

    llm_task_core = MagicMock()
    llm_task_core.async_run = AsyncMock(return_value="AI Output")
    llm_task_core.get_uis.return_value = [ui_with_markdown, ui_without_markdown]

    res = await runner.run_non_interactive_session(
        ctx=ctx,
        llm_task_core=llm_task_core,
        history_manager=MagicMock(),
        ui_commands={},
        initial_message="hi",
        initial_conversation_name="sess1",
        initial_yolo=False,
        initial_attachments=[],
    )

    assert res == "AI Output"
    ui_with_markdown.append_markdown.assert_called_once_with("AI Output")


@pytest.mark.asyncio
async def test_run_non_interactive_session_skips_finalize_for_non_string_result(
    runner,
):
    """A non-string result (e.g. from a tool-only turn) must not reach
    append_markdown -- it isn't renderable markdown."""
    ctx = MagicMock()
    ctx.shared_print = MagicMock()
    ctx.xcom = {}

    ui_with_markdown = MagicMock(spec=["append_markdown"])

    llm_task_core = MagicMock()
    llm_task_core.async_run = AsyncMock(return_value=None)
    llm_task_core.get_uis.return_value = [ui_with_markdown]

    res = await runner.run_non_interactive_session(
        ctx=ctx,
        llm_task_core=llm_task_core,
        history_manager=MagicMock(),
        ui_commands={},
        initial_message="hi",
        initial_conversation_name="sess1",
        initial_yolo=False,
        initial_attachments=[],
    )

    assert res is None
    ui_with_markdown.append_markdown.assert_not_called()


@pytest.mark.asyncio
async def test_run_non_interactive_session_attaches_ui_factories(runner):
    """UI factories are resolved and attached to the core task as output sinks
    so the web/SSE path streams the response without the interactive UI loop."""
    ctx = MagicMock()
    ctx.shared_print = MagicMock()
    ctx.xcom = {}

    http_ui = MagicMock()
    factory = MagicMock(return_value=http_ui)
    runner.llm_chat_task.ui_factories = [factory]

    llm_task_core = MagicMock()
    llm_task_core.async_run = AsyncMock(return_value="AI Output")

    res = await runner.run_non_interactive_session(
        ctx=ctx,
        llm_task_core=llm_task_core,
        history_manager=MagicMock(),
        ui_commands={},
        initial_message="hi",
        initial_conversation_name="sess1",
        initial_yolo=False,
        initial_attachments=[],
    )

    assert res == "AI Output"
    factory.assert_called_once()
    llm_task_core.append_ui.assert_called_once_with(http_ui)


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
            "copy",
            "voice",
            "photo",
            "build",
        ]
    }

    mock_ui = SimpleMockUI()

    with patch("zrb.llm.ui.default.ui.UI", return_value=mock_ui):
        res = await runner.run_interactive_session(
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
    runner.llm_chat_task.ui_factories = [lambda **kwargs: SimpleMockUI(**kwargs)]
    runner.llm_chat_task.include_default_ui = False
    runner.llm_chat_task.approval_channels = [MagicMock(), MagicMock()]

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
            "copy",
            "voice",
            "photo",
            "build",
        ]
    }

    mock_multi = MagicMock()
    mock_multi.run_async = AsyncMock(return_value="MultiResult")
    mock_multi.last_output = "MultiResult"

    with (
        patch("zrb.llm.ui.multi_ui.MultiUI", return_value=mock_multi),
        patch("zrb.llm.approval.multiplex_approval_channel.MultiplexApprovalChannel"),
    ):
        res = await runner.run_interactive_session(
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


@pytest.mark.asyncio
async def test_run_interactive_session_resolves_custom_command_initial_message(
    runner, ui_commands
):
    """A slash-command initial_message must be resolved to its prompt before
    reaching the UI, mirroring run_non_interactive_session's behavior."""
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

    with patch("zrb.llm.ui.default.ui.UI") as MockUI:
        MockUI.return_value = mock_ui

        res = await runner.run_interactive_session(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message="/foo bar",
            initial_conversation_name="sess1",
            initial_yolo=False,
            initial_attachments=[],
        )

        assert res == "Final"
        assert MockUI.call_args.kwargs["initial_message"] == "RESOLVED:bar"


@pytest.mark.asyncio
async def test_run_interactive_session_leaves_plain_message_unchanged(
    runner, ui_commands
):
    """A plain (non-slash-command) initial_message must pass through as-is,
    even when custom commands are registered."""
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

    with patch("zrb.llm.ui.default.ui.UI") as MockUI:
        MockUI.return_value = mock_ui

        res = await runner.run_interactive_session(
            ctx=ctx,
            llm_task_core=llm_task_core,
            history_manager=history_manager,
            ui_commands=ui_commands,
            initial_message="hello there",
            initial_conversation_name="sess1",
            initial_yolo=False,
            initial_attachments=[],
        )

        assert res == "Final"
        assert MockUI.call_args.kwargs["initial_message"] == "hello there"


def test_load_session_history_uses_replay_when_available(runner):
    """When a UI exposes replay_history, it must be used to render loaded history."""
    history_manager = MagicMock()
    history_manager.load.return_value = ["msg1", "msg2"]

    ui = MagicMock(spec=["replay_history", "append_to_output"])
    ui.replay_history = MagicMock()

    runner.load_session_history(ui, history_manager, "sess1")

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
        runner.load_session_history(ui, history_manager, "sess1")

    assert ui.appended == ["FORMATTED"]


def test_load_session_history_empty_name_is_noop(runner):
    """An empty conversation name must short-circuit the loader."""
    history_manager = MagicMock()
    ui = MagicMock(spec=["replay_history", "append_to_output"])

    runner.load_session_history(ui, history_manager, "")

    history_manager.load.assert_not_called()
    ui.replay_history.assert_not_called()


def test_load_session_history_missing_file_is_silent(runner):
    """FileNotFoundError from the history manager must not surface to the user."""
    history_manager = MagicMock()
    history_manager.load.side_effect = FileNotFoundError("no such session")
    ui = MagicMock(spec=["replay_history", "append_to_output"])

    # Should not raise
    runner.load_session_history(ui, history_manager, "sess-missing")

    ui.replay_history.assert_not_called()


# ── @agent-name mention resolution ──


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

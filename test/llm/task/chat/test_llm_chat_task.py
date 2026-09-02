from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.context.shared_context import SharedContext
from zrb.llm.approval import NullApprovalChannel
from zrb.llm.history_manager.any_history_manager import AnyHistoryManager
from zrb.llm.prompt.manager import PromptManager
from zrb.llm.prompt.registry import PromptRegistry
from zrb.llm.task.chat.execution import parse_yolo_value
from zrb.llm.task.chat.task import LLMChatTask
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.session.session import Session


class TestParseYoloValue:
    """Test parse_yolo_value function for selective YOLO support."""

    def test_boolean_true_returns_true(self):
        """Test that boolean True returns True."""
        assert parse_yolo_value(True) is True

    def test_boolean_false_returns_false(self):
        """Test that boolean False returns False."""
        assert parse_yolo_value(False) is False

    def test_empty_string_returns_false(self):
        """Test that empty string returns False."""
        assert parse_yolo_value("") is False

    def test_none_returns_false(self):
        """Test that None returns False."""
        assert parse_yolo_value(None) is False

    def test_string_false_returns_false(self):
        """Test that 'false' returns False."""
        assert parse_yolo_value("false") is False
        assert parse_yolo_value("FALSE") is False
        assert parse_yolo_value("False") is False

    def test_string_zero_returns_false(self):
        """Test that '0' returns False."""
        assert parse_yolo_value("0") is False

    def test_string_no_returns_false(self):
        """Test that 'no' returns False."""
        assert parse_yolo_value("no") is False
        assert parse_yolo_value("NO") is False

    def test_string_none_returns_false(self):
        """Test that 'none' returns False."""
        assert parse_yolo_value("none") is False
        assert parse_yolo_value("None") is False

    def test_string_true_returns_true(self):
        """Test that 'true' returns True."""
        assert parse_yolo_value("true") is True
        assert parse_yolo_value("TRUE") is True
        assert parse_yolo_value("True") is True

    def test_string_one_returns_true(self):
        """Test that '1' returns True."""
        assert parse_yolo_value("1") is True

    def test_string_yes_returns_true(self):
        """Test that 'yes' returns True."""
        assert parse_yolo_value("yes") is True
        assert parse_yolo_value("YES") is True

    def test_single_tool_name_returns_frozenset(self):
        """Test that a single tool name returns a frozenset."""
        result = parse_yolo_value("Write")
        assert result == frozenset({"Write"})

    def test_comma_separated_tools_returns_frozenset(self):
        """Test that comma-separated tool names return a frozenset."""
        result = parse_yolo_value("Write,Edit")
        assert result == frozenset({"Write", "Edit"})

    def test_comma_separated_with_spaces_returns_frozenset(self):
        """Test that tool names with spaces are trimmed."""
        result = parse_yolo_value("Write, Edit, Read")
        assert result == frozenset({"Write", "Edit", "Read"})

    def test_set_returns_frozenset(self):
        """Test that a set returns a frozenset."""
        result = parse_yolo_value({"Write", "Edit"})
        assert result == frozenset({"Write", "Edit"})

    def test_frozenset_returns_frozenset(self):
        """Test that a frozenset returns unchanged."""
        input_set = frozenset({"Write", "Edit"})
        result = parse_yolo_value(input_set)
        assert result == input_set

    def test_empty_comma_separated_returns_false(self):
        """Test that empty comma-separated returns False."""
        assert parse_yolo_value("   ,  ,  ") is False

    def test_whitespace_string_returns_false(self):
        """Test that whitespace-only string returns False."""
        assert parse_yolo_value("   ") is False


@pytest.mark.asyncio
async def test_interactive_teardown_fires_terminal_session_end():
    """SESSION_END fires once when the interactive chat session tears down
    (Claude-compatible: terminal, not per-turn)."""
    from zrb.llm.hook.interface import HookContext, HookResult
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.types import HookEvent

    fired: list[str] = []

    async def record(context: HookContext) -> HookResult:
        fired.append(context.event.value)
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.add_hook(record, events=[HookEvent.SESSION_END])

    task = LLMChatTask(name="teardown-task")
    task.active_hook_manager = manager

    await task.teardown_interactive_resources()

    assert fired == ["SessionEnd"]


@pytest.mark.asyncio
async def test_interactive_teardown_shuts_down_the_session_hook_manager():
    """Teardown must settle the manager the session's hooks actually ran on.

    Regression: it shut down the module-level singleton, but
    _create_llm_task_core builds a fresh HookManager per execution and that is
    the instance every hook is dispatched through — so the singleton held none of
    this session's tasks and detached async hooks outlived the session.
    """
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.types import HookEvent

    manager = HookManager(search_dirs=[])
    manager.parse_and_register(
        {
            "name": "slow-async",
            "events": ["Stop"],
            "type": "command",
            "async": True,
            "config": {"command": "sleep 5", "shell": True},
        },
        "test",
    )
    await manager.execute_hooks(HookEvent.STOP, {})
    assert manager.has_pending_background_hooks

    task = LLMChatTask(name="teardown-task-bg")
    task.active_hook_manager = manager

    await task.teardown_interactive_resources()

    assert not manager.has_pending_background_hooks


@pytest.mark.asyncio
async def test_interactive_teardown_without_hook_manager_is_safe():
    """Teardown must not raise when no hook manager was set (e.g. session never
    reached _create_llm_task_core)."""
    task = LLMChatTask(name="teardown-task-none")
    # active_hook_manager defaults to None; teardown should be a no-op.
    await task.teardown_interactive_resources()


@pytest.mark.asyncio
async def test_llm_chat_task_non_interactive_run():
    """Test LLMChatTask in non-interactive mode."""
    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("AI response", [])

        task = LLMChatTask(
            name="non-interactive-task", message="Hello AI", interactive=False
        )

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())

        result = await task.async_run(session)
        assert result == "AI response"
        assert mock_run_agent.called


@pytest.mark.asyncio
async def test_llm_chat_task_interactive_ui_trigger():
    """Test that LLMChatTask triggers UI in interactive mode."""
    # We mock UI.run_async to avoid launching the actual terminal app
    with patch(
        "zrb.llm.ui.default.ui.UI.run_async", new_callable=AsyncMock
    ) as mock_ui_run:
        task = LLMChatTask(name="interactive-task", interactive=True)

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())

        # We need to mock some UI attributes that might be rendered
        with patch("zrb.util.attr.get_str_attr", return_value=""):
            await task.async_run(session)

        assert mock_ui_run.called


@pytest.mark.asyncio
async def test_llm_chat_task_tool_factories():
    """Test tool and toolset factory resolution via public execution."""

    # Create a real callable function instead of MagicMock
    async def mock_tool_func():
        return "mock_tool_result"

    async def mock_tool_in_toolset_func():
        return "mock_toolset_result"

    # Create proper mock objects with required attributes
    mock_tool = mock_tool_func
    mock_tool_in_toolset = mock_tool_in_toolset_func

    task = LLMChatTask(
        name="factory-task",
        tool_factories=[lambda ctx: mock_tool],
        toolset_factories=[lambda ctx: [mock_tool_in_toolset]],
        interactive=False,
    )
    shared_ctx = SharedContext()
    session = Session(shared_ctx, state_logger=MagicMock())

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])
        await task.async_run(session)

        # Verify that tools from factories were passed to run_agent
        assert mock_run_agent.called
        # The test passes if we reach here without pydantic-ai type inspection errors


@pytest.mark.asyncio
async def test_llm_chat_task_setters():
    """Test various setter methods of LLMChatTask via public execution."""

    # Create real callable functions instead of MagicMock
    async def setter_tool_func():
        return "setter_tool_result"

    async def setter_toolset_func():
        return "setter_toolset_result"

    task = LLMChatTask(name="setter-task", interactive=False)

    task.append_tool(setter_tool_func)
    task.append_toolset(setter_toolset_func)
    task.append_history_processor(MagicMock())
    task.append_trigger(lambda: None)
    task.append_custom_command(MagicMock())

    shared_ctx = SharedContext()
    session = Session(shared_ctx, state_logger=MagicMock())

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])
        await task.async_run(session)
        assert mock_run_agent.called


def test_llm_chat_task_approval_channels_property():
    """Test that the approval_channels property works on LLMChatTask."""
    task = LLMChatTask(name="test-task")

    # Set approval channel programmatically
    channel = NullApprovalChannel()
    task.approval_channels = [channel]

    assert task.approval_channels == [channel]


def test_llm_chat_task_set_uis():
    """Test that set_uis works on LLMChatTask."""
    task = LLMChatTask(name="test-task")

    # Set UI programmatically
    mock_ui = MagicMock(spec=UIProtocol)
    task.set_uis([mock_ui])

    assert task.uis == [mock_ui]


def test_llm_chat_task_ui_factories_property():
    """Test that the ui_factories property works on LLMChatTask."""
    task = LLMChatTask(name="test-task")

    # Set UI factory programmatically
    def mock_factory(*args, **kwargs):
        return MagicMock(spec=UIProtocol)

    task.ui_factories = [mock_factory]

    assert task.ui_factories == [mock_factory]


ORDERED_COLLECTION_STEMS = [
    ("tool", "tools"),
    ("tool_factory", "tool_factories"),
    ("toolset", "toolsets"),
    ("toolset_factory", "toolset_factories"),
    ("history_processor", "history_processors"),
    ("trigger", "triggers"),
    ("custom_command", "custom_commands"),
    ("hook_factory", "hook_factories"),
    ("tool_policy", "tool_policies"),
    ("response_handler", "response_handlers"),
    ("argument_formatter", "argument_formatters"),
    ("ui", "uis"),
    ("ui_factory", "ui_factories"),
    ("approval_channel", "approval_channels"),
]


@pytest.mark.parametrize("stem,plural", ORDERED_COLLECTION_STEMS)
def test_ordered_collection_verbs_round_trip(stem, plural):
    """append_X/prepend_X/set_X/remove_X round-trip on every R5 collection.

    `argument_formatters` starts with two built-in defaults already appended
    at construction (`replace_in_file_formatter`, `write_file_formatter`), so
    assertions are relative to whatever was already there rather than
    assuming an empty list.
    """
    task = LLMChatTask(name="t")
    before = list(getattr(task, plural))
    a, b = object(), object()

    getattr(task, f"append_{stem}")(a)
    assert list(getattr(task, plural)) == before + [a]

    getattr(task, f"prepend_{stem}")(b)
    assert list(getattr(task, plural)) == [b] + before + [a]

    getattr(task, f"remove_{stem}")(b)
    assert list(getattr(task, plural)) == before + [a]

    getattr(task, f"remove_{stem}")(b)  # not present: no-op, not an error
    assert list(getattr(task, plural)) == before + [a]

    # ui_factories/approval_channels replace wholesale through their already
    # settable property rather than a set_X() method (R7 — see
    # framework-conventions.md's "Component slot vs. collection").
    c = object()
    if hasattr(task, f"set_{plural}"):
        getattr(task, f"set_{plural}")([c])
    else:
        setattr(task, plural, [c])
    assert list(getattr(task, plural)) == [c]


# --- R8: the three ADR-0091 configuration channels, each named -------------


def test_a_user_can_swap_the_prompt_manager_after_the_task_is_defined():
    """Channel 3 — a per-task argument overrides one host."""
    # Arrange — a task defined before any user config, as builtin/ does
    task = LLMChatTask(name="chat")
    replacement = PromptManager(prompt_registry=PromptRegistry())

    # Act — what a zrb_init.py does
    task.prompt_manager = replacement

    # Assert
    assert task.prompt_manager is replacement


def test_a_registry_delta_reaches_a_task_built_around_it():
    """Channel 2 — zrb_init.py builds/replaces things on a registry."""
    registry = PromptRegistry()
    registry.append_prompt("Always answer in British English.")

    task = LLMChatTask(
        name="chat", prompt_manager=PromptManager(prompt_registry=registry)
    )

    composed = task.prompt_manager.compose_prompt()(SharedContext())
    assert "Always answer in British English." in composed


def test_a_cfg_scalar_reaches_a_task_that_defers_to_the_registry(monkeypatch):
    """Channel 1 — an env var / CFG twin narrows or seeds the default layer a
    task defers to, with no code change on the task itself."""
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_PROMPT", ["Prefer git over GUI."])
    task = LLMChatTask(name="chat")  # no prompt_manager passed -> defers to CFG

    composed = task.prompt_manager.compose_prompt()(SharedContext())
    assert "Prefer git over GUI." in composed


def test_llm_chat_task_init_with_approval_channel():
    """Test that LLMChatTask accepts approval_channel parameter."""
    channel = NullApprovalChannel()
    task = LLMChatTask(name="test-task", approval_channel=channel)

    # Verify initialization works - behavior tested through async_run
    assert task.name == "test-task"


def test_llm_chat_task_init_with_ui():
    """Test that LLMChatTask accepts ui parameter."""
    mock_ui = MagicMock(spec=UIProtocol)
    task = LLMChatTask(name="test-task", ui=mock_ui)

    # Verify initialization works - behavior tested through async_run
    assert task.name == "test-task"


def test_llm_chat_task_custom_model_names_constructor_and_property():
    names = ["my-model", "other-model"]
    task = LLMChatTask(name="test-task", custom_model_names=names)
    assert task.custom_model_names == names


def test_llm_chat_task_custom_model_names_setter():
    task = LLMChatTask(name="test-task")
    task.custom_model_names = ["updated-model"]
    assert task.custom_model_names == ["updated-model"]


def test_llm_chat_task_model_getter_via_config():
    from zrb.llm.config.config import LLMConfig

    getter = lambda m: "fixed-model"
    config = LLMConfig()
    config.model_getter = getter
    task = LLMChatTask(name="test-task", llm_config=config)
    assert task.llm_config.model_getter is getter


def test_llm_chat_task_model_renderer_via_config():
    from zrb.llm.config.config import LLMConfig

    renderer = lambda m: m
    config = LLMConfig()
    config.model_renderer = renderer
    task = LLMChatTask(name="test-task", llm_config=config)
    assert task.llm_config.model_renderer is renderer


def test_llm_chat_task_custom_model_names_none_by_default():
    task = LLMChatTask(name="test-task")
    assert task.custom_model_names is None


@pytest.mark.asyncio
async def test_llm_chat_task_passes_getter_renderer_to_summarizer():
    """LLMChatTask forwards effective getter/renderer to create_summarizer_history_processor via config."""
    from zrb.llm.config.config import LLMConfig

    getter = lambda m: "getter-model"
    renderer = lambda m: "renderer-model"

    config = LLMConfig()
    config.model_getter = getter
    config.model_renderer = renderer
    task = LLMChatTask(
        name="test-task",
        llm_config=config,
        interactive=False,
    )

    with (
        patch(
            "zrb.llm.task.chat.execution.create_summarizer_history_processor"
        ) as mock_create_proc,
        patch("zrb.llm.task.llm_task.create_agent"),
        patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
    ):
        mock_proc = MagicMock()
        mock_proc.return_value = AsyncMock(return_value=[])
        mock_create_proc.return_value = mock_proc
        mock_run_agent.return_value = ("Done", [])

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())
        await task.async_run(session)

    mock_create_proc.assert_called_once()


def test_llm_chat_task_permissions_constructor_and_property():
    from zrb.llm.permission import ALLOW, PermissionPolicy, Rule

    policy = PermissionPolicy((Rule("*", ALLOW),))
    task = LLMChatTask(name="test-task", permissions=policy)
    assert task.permissions is policy


def test_llm_chat_task_permissions_setter():
    from zrb.llm.permission import DENY, PermissionPolicy, Rule

    policy = PermissionPolicy((Rule("*", DENY),))
    task = LLMChatTask(name="test-task")
    assert task.permissions is None
    task.permissions = policy
    assert task.permissions is policy


@pytest.mark.asyncio
async def test_llm_chat_task_forwards_permissions_to_run_agent():
    """The permissions policy reaches run_agent as permission_policy."""
    from zrb.llm.permission import ASK, PermissionPolicy, Rule

    policy = PermissionPolicy((Rule("Edit", ASK), Rule("*", ASK)))
    task = LLMChatTask(
        name="perm-forward-task",
        message="Hello",
        permissions=policy,
        interactive=False,
    )

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())
        await task.async_run(session)

    assert mock_run_agent.called
    assert mock_run_agent.call_args.kwargs["permission_policy"] is policy


def test_llm_chat_task_history_config_reflects_constructor_values():
    manager = MagicMock()
    task = LLMChatTask(
        name="test-task",
        history_manager=manager,
        conversation_name="my-convo",
        render_conversation_name=False,
    )
    config = task.history_config
    assert config.history_manager is manager
    assert config.conversation_name == "my-convo"
    assert config.render_conversation_name is False


def test_llm_chat_task_history_config_reflects_history_manager_setter_immediately():
    task = LLMChatTask(name="test-task")
    new_manager = MagicMock(spec=AnyHistoryManager)
    task.history_manager = new_manager
    assert task.history_config.history_manager is new_manager


def test_llm_chat_task_history_manager_setter_rejects_wrong_type():
    task = LLMChatTask(name="test-task")
    with pytest.raises(TypeError, match="AnyHistoryManager"):
        task.history_manager = "not a manager"


def test_llm_chat_task_sandbox_constructor_and_property():
    from zrb.llm.sandbox import SandboxPolicy

    policy = SandboxPolicy(enabled=True)
    task = LLMChatTask(name="test-task", sandbox=policy)
    assert task.sandbox is policy


def test_llm_chat_task_sandbox_setter():
    from zrb.llm.sandbox import SandboxPolicy

    policy = SandboxPolicy(enabled=True)
    task = LLMChatTask(name="test-task")
    assert task.sandbox is None
    task.sandbox = policy
    assert task.sandbox is policy


@pytest.mark.asyncio
async def test_llm_chat_task_forwards_sandbox_to_run_agent():
    """The sandbox policy reaches run_agent as sandbox_policy."""
    from zrb.llm.sandbox import SandboxPolicy

    policy = SandboxPolicy(enabled=True)
    task = LLMChatTask(
        name="sandbox-forward-task",
        message="Hello",
        sandbox=policy,
        interactive=False,
    )

    with patch(
        "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Done", [])

        shared_ctx = SharedContext()
        session = Session(shared_ctx, state_logger=MagicMock())
        await task.async_run(session)

    assert mock_run_agent.called
    assert mock_run_agent.call_args.kwargs["sandbox_policy"] is policy


@pytest.mark.asyncio
async def test_non_interactive_run_settles_its_background_hooks():
    """A one-shot run must not leave detached hooks running after it returns.

    Regression: only the interactive path had a teardown, so `zrb llm chat -m
    "..."` and the web/SSE runner left their `async: true` hooks alive — they sit
    in their own process group, so nothing else reaps them. Drained rather than
    cancelled up front: this fires at *run* end, possibly moments after the hook
    was dispatched.
    """
    from zrb.llm.hook.manager import HookManager

    with (
        patch(
            "zrb.llm.task.llm_task.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch.object(HookManager, "shutdown", new_callable=AsyncMock) as mock_shutdown,
    ):
        mock_run_agent.return_value = ("AI response", [])
        task = LLMChatTask(
            name="non-interactive-hook-teardown", message="Hi", interactive=False
        )
        await task.async_run(Session(SharedContext(), state_logger=MagicMock()))

    mock_shutdown.assert_awaited_once_with(drain=True)

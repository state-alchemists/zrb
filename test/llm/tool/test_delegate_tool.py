from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.tool.delegate import BufferedUI, create_delegate_to_agent_tool


@pytest.fixture
def mock_sub_agent_manager():
    manager = MagicMock(spec=SubAgentManager)
    # Setup scan return value
    agent_def = SubAgentDefinition(
        name="test-agent",
        path="path",
        description="A test agent",
        system_prompt="prompt",
    )
    manager.scan.return_value = [agent_def]
    return manager


def test_create_delegate_tool_docstring(mock_sub_agent_manager):
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    assert "test-agent" in tool.__doc__
    assert "A test agent" in tool.__doc__


@pytest.mark.asyncio
async def test_delegate_tool_agent_not_found(mock_sub_agent_manager):
    mock_sub_agent_manager.create_agent.return_value = None
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    result = await tool(
        agent_name="non-existent",
        deliverable="a result",
        task="task",
        non_goals=[],
    )
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_delegate_tool_success(mock_sub_agent_manager):
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("Agent Result", [])

        result = await tool(
            agent_name="test-agent",
            deliverable="updated foo.py",
            task="do this",
            non_goals=["do not refactor unrelated code"],
            additional_context="context",
        )

        assert "test-agent" in result
        assert "completed:" in result
        assert "Agent Result" in result

        # Verify call arguments
        mock_run_agent.assert_called_once()
        call_kwargs = mock_run_agent.call_args.kwargs
        assert call_kwargs["agent"] == mock_agent
        message = call_kwargs["message"]
        # Envelope must fence the sub-agent before any free-form prose
        assert "DELIVERABLE: updated foo.py" in message
        assert "NON-GOALS" in message
        assert "do not refactor unrelated code" in message
        assert "do this" in message
        assert "context" in message
        assert "BEFORE RETURNING" in message
        assert isinstance(call_kwargs["ui"], BufferedUI)


@pytest.mark.asyncio
async def test_delegate_fires_subagent_start_stop(mock_sub_agent_manager):
    """Delegation fires SubagentStart before and SubagentStop after the run, on
    the parent run's hook manager, with a shared agent_id and agent_type=name."""
    from zrb.llm.agent.run.runner import current_hook_manager
    from zrb.llm.hook.interface import HookContext, HookResult
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.types import HookEvent

    mock_sub_agent_manager.create_agent.return_value = MagicMock()

    events: list = []

    async def rec(context: HookContext) -> HookResult:
        events.append((context.event, context.agent_type, context.agent_id))
        return HookResult()

    manager = HookManager(search_dirs=[])
    manager.register(rec, events=[HookEvent.SUBAGENT_START, HookEvent.SUBAGENT_STOP])

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    token = current_hook_manager.set(manager)
    try:
        with patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("ok", [])
            await tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
    finally:
        current_hook_manager.reset(token)

    assert events[0][0] == HookEvent.SUBAGENT_START
    assert events[-1][0] == HookEvent.SUBAGENT_STOP
    # agent_type is the delegated name; start and stop share one agent_id.
    assert all(agent_type == "test-agent" for (_e, agent_type, _id) in events)
    assert len({agent_id for (_e, _t, agent_id) in events}) == 1


@pytest.mark.asyncio
async def test_delegate_tool_empty_non_goals_renders_none_declared(
    mock_sub_agent_manager,
):
    """Empty non_goals list still produces a visible placeholder in the envelope."""
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("ok", [])
        await tool(
            agent_name="test-agent",
            deliverable="d",
            task="t",
            non_goals=[],
        )
        message = mock_run_agent.call_args.kwargs["message"]
        assert "(none declared)" in message


@pytest.mark.asyncio
async def test_delegate_tool_exception(mock_sub_agent_manager):
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch("zrb.llm.tool.delegate.run_agent", side_effect=Exception("Run failed")):
        result = await tool(
            agent_name="test-agent",
            deliverable="d",
            task="task",
            non_goals=[],
        )
        assert "Error:" in result
        assert "Run failed" in result


# BufferedUI Tests
def test_buffered_ui_append_to_output():
    """Test BufferedUI buffers output correctly."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    ui.append_to_output("Line 1")
    ui.append_to_output("Line 2")

    # Output should be buffered, not written yet
    # append_to_output adds end="\n" by default, so we get "Line 1\n" and "Line 2\n"
    buffered = ui.get_buffered_output()
    assert "Line 1" in buffered
    assert "Line 2" in buffered
    # Nothing should be written to wrapped UI yet
    assert mock_wrapped.append_to_output.call_count == 0


def test_buffered_ui_flush_to_parent():
    """Test BufferedUI flush_to_parent with prefix."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    ui.append_to_output("Line 1\nLine 2")
    ui.flush_to_parent()

    # Should have called append_to_output with prefixed content
    assert mock_wrapped.append_to_output.call_count == 1
    # Check that the call contains the prefixed lines
    call_arg = mock_wrapped.append_to_output.call_args[0][0]
    assert "[AGENT]" in call_arg


def test_buffered_ui_clear_buffer():
    """Test BufferedUI clear_buffer clears output."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    ui.append_to_output("Some content")
    assert "Some content" in ui.get_buffered_output()

    ui.clear_buffer()
    assert ui.get_buffered_output() == ""


@pytest.mark.asyncio
async def test_buffered_ui_ask_user():
    """Test BufferedUI ask_user forwards to parent with prefix."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user = AsyncMock(return_value="user response")
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")

    result = await ui.ask_user("What should I do?")

    assert result == "user response"
    mock_wrapped.ask_user.assert_called_once()
    # Check prefix was added
    call_arg = mock_wrapped.ask_user.call_args[0][0]
    assert "[AGENT]" in call_arg
    assert "What should I do?" in call_arg


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_no_prefix():
    """Test BufferedUI ask_user without prefix."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user = AsyncMock(return_value="response")
    ui = BufferedUI(mock_wrapped, prefix="")

    result = await ui.ask_user("Question?")

    assert result == "response"
    # No prefix should be added
    mock_wrapped.ask_user.assert_called_with("Question?")


# --- #3: permission-filtered agent roster --------------------------------


@pytest.fixture
def two_agent_manager():
    manager = MagicMock(spec=SubAgentManager)
    manager.scan.return_value = [
        SubAgentDefinition(
            name="explorer", path="p1", description="reads code", system_prompt="x"
        ),
        SubAgentDefinition(
            name="builder", path="p2", description="writes code", system_prompt="y"
        ),
    ]
    return manager


def test_docstring_lists_all_agents_without_policy(two_agent_manager):
    tool = create_delegate_to_agent_tool(two_agent_manager)
    assert "explorer" in tool.__doc__
    assert "builder" in tool.__doc__


def test_docstring_filters_denied_agent(two_agent_manager):
    from zrb.llm.permission import PermissionPolicy, Rule, current_permission_policy

    # Deny delegating to the "builder" agent specifically (arg_pattern on
    # agent_name), allow the rest.
    policy = PermissionPolicy(
        (
            Rule("DelegateToAgent", "deny", arg_pattern="builder"),
            Rule("*", "allow"),
        )
    )
    token = current_permission_policy.set(policy)
    try:
        tool = create_delegate_to_agent_tool(two_agent_manager)
    finally:
        current_permission_policy.reset(token)

    assert "explorer" in tool.__doc__
    assert "builder" not in tool.__doc__


# ── Fan-out (tasks=) tests — merged from the former DelegateToAgentsParallel ──


def test_delegate_docstring_mentions_fan_out(two_agent_manager):
    tool = create_delegate_to_agent_tool(two_agent_manager)
    assert "FAN OUT" in tool.__doc__
    assert "tasks" in tool.__doc__


@pytest.mark.asyncio
async def test_delegate_missing_args_without_tasks(mock_sub_agent_manager):
    """No flat args and no tasks → actionable missing-args error."""
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    result = await tool()
    assert "missing required args" in result
    assert "tasks=" in result


@pytest.mark.asyncio
async def test_delegate_fan_out_missing_keys(mock_sub_agent_manager):
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    result = await tool(tasks=[{"agent_name": "explorer"}])
    assert "missing required keys" in result


@pytest.mark.asyncio
async def test_delegate_fan_out_validates_all_tasks(mock_sub_agent_manager):
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    result = await tool(
        tasks=[
            {
                "agent_name": "explorer",
                "deliverable": "x",
                "task": "y",
                "non_goals": [],
            },
            {"agent_name": "builder"},
        ]
    )
    assert "tasks[1]" in result


@pytest.mark.asyncio
async def test_delegate_fan_out_runs_all_and_combines(mock_sub_agent_manager):
    """tasks=[...] runs each sub-agent and returns their results together."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.side_effect = [("Result A", []), ("Result B", [])]
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "a",
                    "task": "ta",
                    "non_goals": [],
                },
                {
                    "agent_name": "test-agent",
                    "deliverable": "b",
                    "task": "tb",
                    "non_goals": [],
                },
            ]
        )

    assert mock_run_agent.call_count == 2
    assert "Result A" in result
    assert "Result B" in result
    assert result.count("completed:") == 2


# ── BufferedUI: passthrough methods, prefix branches, activity routing ──


@pytest.mark.asyncio
async def test_buffered_ui_ask_user_choice_flushes_and_forwards():
    """ask_user_choice flushes buffered output first, then forwards to parent."""
    mock_wrapped = MagicMock()
    mock_wrapped.ask_user_choice = AsyncMock(return_value="option-a")
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")
    ui.append_to_output("buffered line")

    spec = MagicMock()
    result = await ui.ask_user_choice(spec)

    assert result == "option-a"
    mock_wrapped.ask_user_choice.assert_awaited_once_with(spec)
    # Buffered output was flushed to the parent before asking.
    mock_wrapped.append_to_output.assert_called()


@pytest.mark.asyncio
async def test_buffered_ui_run_interactive_command_forwards():
    """run_interactive_command passes straight through to the wrapped UI."""
    mock_wrapped = MagicMock()
    mock_wrapped.run_interactive_command = AsyncMock(return_value="cmd-output")
    ui = BufferedUI(mock_wrapped)

    result = await ui.run_interactive_command("ls", shell=True)

    assert result == "cmd-output"
    mock_wrapped.run_interactive_command.assert_awaited_once_with("ls", True)


@pytest.mark.asyncio
async def test_buffered_ui_run_async_forwards():
    """run_async passes straight through to the wrapped UI."""
    mock_wrapped = MagicMock()
    mock_wrapped.run_async = AsyncMock(return_value="async-result")
    ui = BufferedUI(mock_wrapped)

    result = await ui.run_async()

    assert result == "async-result"
    mock_wrapped.run_async.assert_awaited_once()


def test_buffered_ui_flush_to_parent_without_prefix():
    """With no prefix, flush writes the raw buffered output verbatim."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="")
    ui.append_to_output("raw line")

    ui.flush_to_parent()

    mock_wrapped.append_to_output.assert_called_once()
    assert mock_wrapped.append_to_output.call_args[0][0] == "raw line\n"


def test_buffered_ui_yolo_delegates_to_wrapped():
    """yolo reads through to the wrapped UI when it exposes the attribute."""

    class _Parent:
        yolo = True

    ui = BufferedUI(_Parent())
    assert ui.yolo is True


def test_buffered_ui_yolo_defaults_false_when_absent():
    """yolo defaults to False when the wrapped UI has no yolo attribute."""

    class _Parent:
        pass

    ui = BufferedUI(_Parent())
    assert ui.yolo is False


def test_buffered_ui_append_to_output_updates_activity_registry():
    """When an activity id is set, buffered writes also feed the activity panel."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped)
    ui.set_activity_id("agent-123")

    with patch("zrb.llm.tool.delegate.agent_activity_registry") as reg:
        ui.append_to_output("line")

    reg.update.assert_called_once()
    assert reg.update.call_args[0][0] == "agent-123"


def test_buffered_ui_stream_to_parent_prefixes_and_feeds_activity():
    """stream_to_parent bypasses the buffer, prefixes each non-empty line, and
    routes to the activity registry when an id is set."""
    mock_wrapped = MagicMock()
    ui = BufferedUI(mock_wrapped, prefix="[AGENT] ")
    ui.set_activity_id("agent-xyz")

    with patch("zrb.llm.tool.delegate.agent_activity_registry") as reg:
        ui.stream_to_parent("first\nsecond")

    reg.update.assert_called_once()
    mock_wrapped.append_to_output.assert_called_once()
    streamed = mock_wrapped.append_to_output.call_args[0][0]
    assert "[AGENT] first" in streamed
    assert "[AGENT] second" in streamed
    # Streaming is immediate: nothing was left in the buffer.
    assert ui.get_buffered_output() == ""


# ── Envelope: non_goals-as-string and active-worktree context ──


@pytest.mark.asyncio
async def test_delegate_non_goals_as_string(mock_sub_agent_manager):
    """A non_goals string (not a list) still renders as a single bullet."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.return_value = ("ok", [])
        await tool(
            agent_name="test-agent",
            deliverable="d",
            task="t",
            non_goals="do not touch prod",
        )
        message = mock_run_agent.call_args.kwargs["message"]
        assert "  - do not touch prod" in message


@pytest.mark.asyncio
async def test_delegate_envelope_includes_active_worktree(mock_sub_agent_manager):
    """When a worktree is active, the envelope CONTEXT names it alongside context."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.get_active_worktree",
            return_value="/repo/.zrb/worktree/feat",
        ),
    ):
        mock_run_agent.return_value = ("ok", [])
        await tool(
            agent_name="test-agent",
            deliverable="d",
            task="t",
            non_goals=[],
            additional_context="existing context",
        )
        message = mock_run_agent.call_args.kwargs["message"]
        assert "Active worktree: /repo/.zrb/worktree/feat" in message
        assert "existing context" in message


@pytest.mark.asyncio
async def test_delegate_active_worktree_without_context(mock_sub_agent_manager):
    """With no additional_context, the worktree line stands alone in CONTEXT."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch("zrb.llm.tool.delegate.get_active_worktree", return_value="/wt"),
    ):
        mock_run_agent.return_value = ("ok", [])
        await tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
        message = mock_run_agent.call_args.kwargs["message"]
        assert "Active worktree: /wt" in message


# ── Error paths: recursion, swallowed hook errors, fan-out failure ──


@pytest.mark.asyncio
async def test_delegate_recursion_error_surfaces_suggestion(mock_sub_agent_manager):
    """A RecursionError from the sub-agent maps to an actionable error string."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent",
        new_callable=AsyncMock,
        side_effect=RecursionError(),
    ):
        result = await tool(
            agent_name="test-agent", deliverable="d", task="t", non_goals=[]
        )

    assert "Recursion depth exceeded" in result


@pytest.mark.asyncio
async def test_delegate_swallows_hook_manager_errors(mock_sub_agent_manager):
    """A hook manager that raises must not break delegation (fire-and-forget)."""
    from zrb.llm.agent.run.runner import current_hook_manager

    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    boom_manager = MagicMock()
    boom_manager.execute_hooks = AsyncMock(side_effect=RuntimeError("hook boom"))

    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    token = current_hook_manager.set(boom_manager)
    try:
        with patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("ok", [])
            result = await tool(
                agent_name="test-agent", deliverable="d", task="t", non_goals=[]
            )
    finally:
        current_hook_manager.reset(token)

    # Delegation succeeds despite the hook manager blowing up.
    assert "completed:" in result
    assert "ok" in result
    boom_manager.execute_hooks.assert_awaited()


@pytest.mark.asyncio
async def test_delegate_fan_out_reports_failed_task(mock_sub_agent_manager):
    """A failing sub-agent in a fan-out surfaces as an Error line; others succeed."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with patch(
        "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
    ) as mock_run_agent:
        mock_run_agent.side_effect = [("Result OK", []), Exception("boom")]
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "a",
                    "task": "ta",
                    "non_goals": [],
                },
                {
                    "agent_name": "test-agent",
                    "deliverable": "b",
                    "task": "tb",
                    "non_goals": [],
                },
            ]
        )

    assert "Result OK" in result
    assert "Error: boom" in result


# ── create_delegate_to_agent_tool: default manager fallback ──


def test_create_delegate_tool_uses_default_manager():
    """Passing no manager falls back to the module default singleton."""
    default = MagicMock(spec=SubAgentManager)
    default.scan.return_value = []

    with patch("zrb.llm.tool.delegate.default_sub_agent_manager", default):
        tool = create_delegate_to_agent_tool()

    assert tool.__name__ == "DelegateToAgent"
    default.scan.assert_called()

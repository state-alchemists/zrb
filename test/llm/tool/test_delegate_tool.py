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

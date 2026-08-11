from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.tool.delegate import (
    BufferedUI,
    agent_not_found_message,
    agent_roster_doc,
    create_delegate_to_agent_tool,
    create_search_agent_tool,
)


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


def _many_agents(count: int) -> list[SubAgentDefinition]:
    return [
        SubAgentDefinition(
            name=f"agent-{i:02d}",
            path="path",
            description=f"Agent {i:02d}",
            system_prompt="prompt",
        )
        for i in range(count)
    ]


def test_agent_roster_doc_truncates_with_search_pointer(
    mock_sub_agent_manager, monkeypatch
):
    """A fleet over the cap lists only the first entries and points at
    SearchAgent for the rest."""
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "3")
    mock_sub_agent_manager.scan.return_value = _many_agents(8)

    doc = agent_roster_doc(mock_sub_agent_manager)

    assert "agent-00" in doc
    assert "agent-02" in doc
    assert "agent-03" not in doc
    assert "5 more" in doc
    assert "SearchAgent" in doc


def test_agent_roster_doc_stays_complete_under_cap(mock_sub_agent_manager, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "3")
    mock_sub_agent_manager.scan.return_value = _many_agents(2)

    doc = agent_roster_doc(mock_sub_agent_manager)

    assert "agent-01" in doc
    assert "more" not in doc


def test_agent_roster_doc_cap_zero_is_unlimited(mock_sub_agent_manager, monkeypatch):
    """0 disables the cap: the whole roster is listed, no truncation note."""
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "0")
    mock_sub_agent_manager.scan.return_value = _many_agents(8)

    doc = agent_roster_doc(mock_sub_agent_manager)

    assert "agent-07" in doc
    assert "more" not in doc


def test_agent_not_found_message_truncates(mock_sub_agent_manager, monkeypatch):
    """The recovery error must not dump a huge roster either — a working
    subset plus a pointer to SearchAgent."""
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "3")
    mock_sub_agent_manager.scan.return_value = _many_agents(8)

    result = agent_not_found_message("nope", mock_sub_agent_manager)

    assert "agent-00" in result
    assert "agent-03" not in result
    assert "5 more" in result
    assert "SearchAgent" in result


class TestSearchAgentTool:
    """SearchAgent: on-demand window onto the truncated agent roster."""

    @pytest.mark.asyncio
    async def test_matches_name(self, mock_sub_agent_manager):
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="test")

        assert "test-agent" in result
        assert "A test agent" in result

    @pytest.mark.asyncio
    async def test_matches_description(self, mock_sub_agent_manager):
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="agent")

        assert "test-agent" in result

    @pytest.mark.asyncio
    async def test_no_match_names_the_way_back(self, mock_sub_agent_manager):
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="nothing")

        assert "No agents match 'nothing'" in result
        assert "[SYSTEM SUGGESTION]" in result

    @pytest.mark.asyncio
    async def test_empty_query_lists_every_delegatable_agent(
        self, mock_sub_agent_manager
    ):
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="")

        assert "test-agent" in result

    @pytest.mark.asyncio
    async def test_truncates_runaway_results(self, mock_sub_agent_manager, monkeypatch):
        mock_sub_agent_manager.scan.return_value = [
            SubAgentDefinition(
                name=f"match-{i:02d}",
                path="path",
                description="shares the keyword",
                system_prompt="prompt",
            )
            for i in range(40)
        ]
        tool = create_search_agent_tool(mock_sub_agent_manager)
        result = await tool(query="keyword")

        assert "match-29" in result
        assert "match-30" not in result
        assert "more match" in result

    def test_is_a_delegate_tool(self, mock_sub_agent_manager):
        """SearchAgent belongs to the delegate family: sub-agents filter it out
        and the `minimal` profile drops it with the rest."""
        tool = create_search_agent_tool(mock_sub_agent_manager)

        assert tool.__name__ == "SearchAgent"
        assert getattr(tool, "zrb_is_delegate_tool", False) is True


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
    # The roster is in the error, so the retry is a correction, not a guess.
    assert "test-agent" in result


@pytest.mark.asyncio
async def test_delegate_tool_not_found_suggests_closest_name(
    mock_sub_agent_manager,
):
    mock_sub_agent_manager.create_agent.return_value = None
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    result = await tool(
        agent_name="test-agnt",
        deliverable="a result",
        task="task",
        non_goals=[],
    )
    assert "Did you mean 'test-agent'?" in result


def test_agent_not_found_message_without_registered_agents():
    manager = MagicMock(spec=SubAgentManager)
    manager.scan.return_value = []

    result = agent_not_found_message("anything", manager)

    assert "no sub-agents are registered" in result
    # No roster to offer, so it must not tell the model to retry with a name.
    assert "Call again" not in result


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

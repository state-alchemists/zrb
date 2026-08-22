import asyncio
import os
import uuid
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


def test_agent_roster_doc_puts_core_agents_first(mock_sub_agent_manager, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MAX_AGENTS_IN_ROSTER", "1")
    core = SubAgentDefinition(
        name="generalist",
        path="src/zrb/llm_plugin/core_agents/generalist.agent.md",
        description="Core generalist",
        system_prompt="prompt",
    )
    optional = SubAgentDefinition(
        name="alpha",
        path="src/zrb/llm_plugin/agents/alpha.agent.md",
        description="Optional agent",
        system_prompt="prompt",
    )
    mock_sub_agent_manager.scan.return_value = [optional, core]

    doc = agent_roster_doc(mock_sub_agent_manager)

    assert "`generalist`" in doc
    assert "`alpha`" not in doc


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
async def test_delegate_passes_live_sessions_run_scope_to_run_agent(
    mock_sub_agent_manager,
):
    """The live-session registry entry's run_scope must reach run_agent, so
    a later continuation of this same sub-agent (live_session.py) can reuse
    it instead of each turn getting its own file_observation.py bucket."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()  # earlier tests may have left sessions
    try:
        mock_agent = MagicMock()
        mock_sub_agent_manager.create_agent.return_value = mock_agent

        tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

        with patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent:
            mock_run_agent.return_value = ("Agent Result", [])

            await tool(
                agent_name="test-agent",
                deliverable="updated foo.py",
                task="do this",
                non_goals=[],
                additional_context="",
            )

            [session] = live_subagent_session_registry.active("default")
            call_kwargs = mock_run_agent.call_args.kwargs
            assert call_kwargs["run_scope"] == session.run_scope
            assert call_kwargs["run_scope"] != ""
    finally:
        # A failed assert must not leak this session into other tests.
        live_subagent_session_registry.clear()


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


@pytest.mark.asyncio
async def test_delegate_human_cancel_returns_gracefully(mock_sub_agent_manager):
    """Esc while viewing a running sub-agent (TUI) cancels only that sub-agent:
    the delegate swallows the human-flagged CancelledError and reports a
    cancelled result, so a main agent awaiting the delegation (e.g. a fan-out's
    `asyncio.gather`) is NOT itself cancelled."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()  # earlier tests may have left sessions
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()  # never finishes on its own

    try:
        with patch("zrb.llm.tool.delegate.run_agent", side_effect=blocking_run_agent):
            run_task = asyncio.create_task(
                tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
            )
            await started.wait()
            [session] = live_subagent_session_registry.active("default")
            # The task driving the delegation is registered as the session's
            # active task; cancelling through the registry is exactly what the
            # TUI's Esc does.
            assert session.active_task is run_task
            assert live_subagent_session_registry.cancel("default", session.agent_id)
            result = await run_task  # completes instead of raising CancelledError
    finally:
        live_subagent_session_registry.clear()

    assert "Cancelled by user" in result


@pytest.mark.asyncio
async def test_delegate_cancel_without_human_flag_propagates(mock_sub_agent_manager):
    """A cancellation NOT flagged by the sub-agent-view Esc (e.g. the main
    run's own Esc) must propagate as CancelledError — swallowing it would
    resurrect a main turn the user explicitly cancelled."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()  # earlier tests may have left sessions
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()

    try:
        with patch("zrb.llm.tool.delegate.run_agent", side_effect=blocking_run_agent):
            run_task = asyncio.create_task(
                tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
            )
            await started.wait()
            [session] = live_subagent_session_registry.active("default")
            assert session.cancelled_by_human is False  # fresh run, flag reset
            run_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await run_task
    finally:
        live_subagent_session_registry.clear()


@pytest.mark.asyncio
async def test_delegate_marks_done_in_live_view_on_success(mock_sub_agent_manager):
    """A completed delegation appends an end-of-session <Done> to the sub-agent's
    live-view transcript — after the turn went idle, so the view visibly ends."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    try:
        with (
            patch(
                "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
            ) as mock_run_agent,
            patch("zrb.llm.tool.delegate.persist_subagent_history"),
        ):
            mock_run_agent.return_value = ("ok", [])
            result = await tool(
                agent_name="test-agent", deliverable="d", task="t", non_goals=[]
            )

        assert "completed:" in result
        [session] = live_subagent_session_registry.active("default")
        assert session.state == "idle"
        assert "<Done>" in session.buffered_ui.get_buffered_output()
    finally:
        live_subagent_session_registry.clear()


@pytest.mark.asyncio
async def test_delegate_cancelled_view_shows_no_done_marker(mock_sub_agent_manager):
    """A human-cancelled delegation must not end with <Done> — the TUI wrote
    <Esc> Canceled, and a <Done> on top would contradict it."""
    from zrb.llm.agent.subagent.live_session import live_subagent_session_registry

    live_subagent_session_registry.clear()
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)
    started = asyncio.Event()

    async def blocking_run_agent(**kwargs):
        started.set()
        await asyncio.Event().wait()

    try:
        with patch("zrb.llm.tool.delegate.run_agent", side_effect=blocking_run_agent):
            run_task = asyncio.create_task(
                tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
            )
            await started.wait()
            [session] = live_subagent_session_registry.active("default")
            live_subagent_session_registry.cancel("default", session.agent_id)
            result = await run_task
            assert "Cancelled by user" in result
            assert "<Done>" not in session.buffered_ui.get_buffered_output()
    finally:
        live_subagent_session_registry.clear()


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


async def _fan_out_tracking_concurrency(count: int):
    """5 identical fan-out task specs, plus an async run_agent stand-in that
    records the maximum number of concurrently in-flight calls.
    """
    tasks = [
        {"agent_name": "a", "deliverable": "d", "task": "t", "non_goals": []}
        for _ in range(count)
    ]
    in_flight = 0
    max_in_flight = 0

    async def fake_run_agent(*args, **kwargs):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return ("ok", [])

    return tasks, fake_run_agent, lambda: max_in_flight


@pytest.mark.asyncio
async def test_delegate_fan_out_respects_parallel_cap(
    mock_sub_agent_manager, monkeypatch
):
    """LLM_MAX_PARALLEL_DELEGATIONS (ADR-0068) bounds how many sub-agent runs
    are in flight at once — a model-requested `tasks` list has no other size
    limit.
    """
    monkeypatch.setenv("ZRB_LLM_MAX_PARALLEL_DELEGATIONS", "2")
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    tasks, fake_run_agent, get_max_in_flight = await _fan_out_tracking_concurrency(5)
    with patch("zrb.llm.tool.delegate.run_agent", side_effect=fake_run_agent):
        result = await tool(tasks=tasks)

    assert get_max_in_flight() <= 2
    assert result.count("completed:") == 5


@pytest.mark.asyncio
async def test_delegate_fan_out_cap_disabled_by_zero(
    mock_sub_agent_manager, monkeypatch
):
    """0 disables the cap, matching LLM_MAX_REQUEST_PER_RUN's convention —
    all tasks run concurrently, as before this fix.
    """
    monkeypatch.setenv("ZRB_LLM_MAX_PARALLEL_DELEGATIONS", "0")
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    tasks, fake_run_agent, get_max_in_flight = await _fan_out_tracking_concurrency(5)
    with patch("zrb.llm.tool.delegate.run_agent", side_effect=fake_run_agent):
        result = await tool(tasks=tasks)

    assert get_max_in_flight() == 5
    assert result.count("completed:") == 5


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
async def test_fire_subagent_hook_swallows_cancelled_error():
    """`_fire_subagent_hook` documents "Never raises" -- `asyncio.CancelledError`
    is a `BaseException`, not caught by a plain `except Exception`, so it must
    be caught explicitly. This call site fires from inside `run_agent_task`'s
    `finally` block (after its result is already decided) and from the top of
    its `try` block -- a stray cancel landing in either window must not
    override an already-settled return or escape uncaught."""
    from zrb.llm.agent.run.runner import current_hook_manager
    from zrb.llm.hook.types import HookEvent
    from zrb.llm.tool.delegate import _fire_subagent_hook

    cancelling_manager = MagicMock()
    cancelling_manager.execute_hooks = AsyncMock(side_effect=asyncio.CancelledError())

    token = current_hook_manager.set(cancelling_manager)
    try:
        # Must not raise.
        await _fire_subagent_hook(HookEvent.SUBAGENT_STOP, "test-agent", "abcd1234")
    finally:
        current_hook_manager.reset(token)

    cancelling_manager.execute_hooks.assert_awaited()


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


# ── Fan-out: opt-in worktree isolation (isolate_worktree) ──


@pytest.mark.asyncio
async def test_isolate_worktree_enters_and_cleans_up_when_clean(mock_sub_agent_manager):
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch(
            "zrb.llm.tool.delegate.get_active_worktree",
            return_value="/repo/.zrb/worktree/x",
        ),
        patch(
            "zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock
        ) as mock_exit,
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.worktree_has_new_commits",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        mock_enter.return_value = "Worktree created: /repo/.zrb/worktree/x\nBranch: b"
        mock_run_agent.return_value = ("done", [])
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                }
            ]
        )

    mock_enter.assert_awaited_once()
    mock_exit.assert_awaited_once_with("/repo/.zrb/worktree/x")
    assert "done" in result
    assert "Worktree left in place" not in result


@pytest.mark.asyncio
async def test_isolate_worktree_leaves_dirty_worktree_and_reports_path(
    mock_sub_agent_manager,
):
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch(
            "zrb.llm.tool.delegate.get_active_worktree",
            return_value="/repo/.zrb/worktree/x",
        ),
        patch(
            "zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock
        ) as mock_exit,
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.worktree_has_new_commits",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        mock_enter.return_value = "Worktree created: /repo/.zrb/worktree/x\nBranch: b"
        mock_run_agent.return_value = ("done", [])
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                }
            ]
        )

    mock_exit.assert_not_called()
    assert "Worktree left in place for review: /repo/.zrb/worktree/x" in result


@pytest.mark.asyncio
async def test_isolate_worktree_leaves_worktree_with_new_commits_and_keeps_branch(
    mock_sub_agent_manager,
):
    """A worktree with no uncommitted diff but commits beyond its fork point
    must be left in place too — a clean `git status` alone must never be
    treated as "safe to force-delete the branch" (the branch may hold a
    sub-agent's committed deliverable)."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch(
            "zrb.llm.tool.delegate.get_active_worktree",
            return_value="/repo/.zrb/worktree/x",
        ),
        patch(
            "zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock
        ) as mock_exit,
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.worktree_has_new_commits",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        mock_enter.return_value = "Worktree created: /repo/.zrb/worktree/x\nBranch: b"
        mock_run_agent.return_value = ("done", [])
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                }
            ]
        )

    mock_exit.assert_not_called()
    assert "Worktree left in place for review: /repo/.zrb/worktree/x" in result


@pytest.mark.asyncio
async def test_isolate_worktree_cleanup_failure_reported_not_raised(
    mock_sub_agent_manager,
):
    """A cleanup failure (e.g. `worktree_has_new_commits` raising) must not
    escape `asyncio.gather` and abort the whole fan-out — it's reported on
    the task's own result instead."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch(
            "zrb.llm.tool.delegate.get_active_worktree",
            return_value="/repo/.zrb/worktree/x",
        ),
        patch("zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock),
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.worktree_has_new_commits",
            new_callable=AsyncMock,
            side_effect=RuntimeError("git binary missing"),
        ),
    ):
        mock_enter.return_value = "Worktree created: /repo/.zrb/worktree/x\nBranch: b"
        mock_run_agent.return_value = ("done", [])
        result = await tool(
            tasks=[
                {
                    "agent_name": "agent-a",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                },
                {
                    "agent_name": "agent-b",
                    "deliverable": "d2",
                    "task": "t2",
                    "non_goals": [],
                },
            ]
        )

    # The failing task's cleanup note is reported, not raised — and its
    # sibling (no isolate_worktree, unaffected) still completes normally.
    assert "Worktree cleanup failed" in result
    assert "git binary missing" in result
    assert "agent-b" in result and "done" in result


@pytest.mark.asyncio
async def test_isolate_worktree_cleans_up_even_when_subagent_errors(
    mock_sub_agent_manager,
):
    """Cleanup must survive a crashed/erroring sub-agent (ADR-0068)."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch(
            "zrb.llm.tool.delegate.get_active_worktree",
            return_value="/repo/.zrb/worktree/x",
        ),
        patch(
            "zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock
        ) as mock_exit,
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.worktree_has_new_commits",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        mock_enter.return_value = "Worktree created: /repo/.zrb/worktree/x\nBranch: b"
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                }
            ]
        )

    mock_exit.assert_awaited_once_with("/repo/.zrb/worktree/x")
    assert "Error: boom" in result


@pytest.mark.asyncio
async def test_fan_out_without_isolate_worktree_skips_worktree_calls(
    mock_sub_agent_manager,
):
    """Default (no isolate_worktree) must not touch worktrees at all."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch(
            "zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock
        ) as mock_exit,
    ):
        mock_run_agent.return_value = ("done", [])
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                }
            ]
        )

    mock_enter.assert_not_called()
    mock_exit.assert_not_called()
    assert "done" in result


@pytest.mark.asyncio
async def test_isolate_worktree_enter_failure_skips_subagent(mock_sub_agent_manager):
    """A failed EnterWorktree must not run the sub-agent at all."""
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree",
            new_callable=AsyncMock,
            return_value="Error: Not inside a git repository.",
        ),
        patch("zrb.llm.tool.delegate.get_active_worktree", return_value=""),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
    ):
        result = await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                }
            ]
        )

    mock_run_agent.assert_not_called()
    assert "Not inside a git repository" in result


@pytest.mark.asyncio
async def test_isolate_worktree_uses_distinct_branch_names_per_task(
    mock_sub_agent_manager,
):
    """Concurrent isolate_worktree tasks must not collide on enter_worktree's
    own (second-granularity) default branch name."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.enter_worktree", new_callable=AsyncMock
        ) as mock_enter,
        patch("zrb.llm.tool.delegate.get_active_worktree", return_value="/wt"),
        patch("zrb.llm.tool.delegate.exit_worktree", new_callable=AsyncMock),
        patch(
            "zrb.llm.tool.delegate.worktree_has_changes",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.worktree_has_new_commits",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        mock_enter.return_value = "Worktree created"
        mock_run_agent.return_value = ("done", [])
        await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                    "isolate_worktree": True,
                },
                {
                    "agent_name": "test-agent",
                    "deliverable": "d2",
                    "task": "t2",
                    "non_goals": [],
                    "isolate_worktree": True,
                },
            ]
        )

    branch_names = [c.kwargs["branch_name"] for c in mock_enter.await_args_list]
    assert len(branch_names) == 2
    assert len(set(branch_names)) == 2


# ── Sub-agent transcript persistence (always-on, bounded by RETAIN) ──


@pytest.mark.asyncio
async def test_subagent_history_persisted(mock_sub_agent_manager, monkeypatch):
    """Every completed delegation persists its transcript; no knob gates it."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch("zrb.llm.tool.delegate.get_current_tool_session", return_value="sess1"),
        patch("zrb.llm.tool.delegate.persist_subagent_history") as mock_persist,
    ):
        mock_run_agent.return_value = ("ok", [{"fake": "message"}])
        result = await tool(
            agent_name="test-agent", deliverable="d", task="t", non_goals=[]
        )

    mock_persist.assert_called_once()
    conversation_name, history = mock_persist.call_args.args
    assert conversation_name.startswith("sess1-sub-test-agent-")
    assert history == [{"fake": "message"}]
    assert f"Transcript saved as '{conversation_name}'" in result


@pytest.mark.asyncio
async def test_subagent_history_persist_failure_does_not_break_delegation(
    mock_sub_agent_manager, monkeypatch
):
    """A persistence error (disk full, permissions) must not surface as a
    delegation failure — best-effort, same posture as the hook firing."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.history_manager.file_history_manager.FileHistoryManager",
            side_effect=OSError("disk full"),
        ),
    ):
        mock_run_agent.return_value = ("ok", [])
        result = await tool(
            agent_name="test-agent", deliverable="d", task="t", non_goals=[]
        )

    assert "completed:" in result
    assert "ok" in result


@pytest.mark.asyncio
async def test_fan_out_persists_history_per_task(mock_sub_agent_manager, monkeypatch):
    """Fan-out shares `run_agent_task`, so each task gets its own persisted
    transcript under a distinct conversation name."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch("zrb.llm.tool.delegate.get_current_tool_session", return_value="sess1"),
        patch("zrb.llm.tool.delegate.persist_subagent_history") as mock_persist,
    ):
        mock_run_agent.side_effect = [("Result A", []), ("Result B", [])]
        await tool(
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

    assert mock_persist.call_count == 2
    names = {c.args[0] for c in mock_persist.call_args_list}
    assert len(names) == 2  # distinct conversation names per task


# ── Activity-panel session scoping (Item 4, Phase D) ──


@pytest.mark.asyncio
async def test_activity_start_and_finish_are_scoped_to_the_current_session(
    mock_sub_agent_manager,
):
    """A process hosting multiple sessions must not bleed one session's
    running sub-agents into another's activity panel/listing."""
    mock_agent = MagicMock()
    mock_sub_agent_manager.create_agent.return_value = mock_agent
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    with (
        patch(
            "zrb.llm.tool.delegate.run_agent", new_callable=AsyncMock
        ) as mock_run_agent,
        patch(
            "zrb.llm.tool.delegate.get_current_tool_session",
            return_value="session-42",
        ),
        patch("zrb.llm.tool.delegate.agent_activity_registry") as mock_registry,
    ):
        mock_run_agent.return_value = ("ok", [])
        await tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])

    mock_registry.start.assert_called_once()
    assert mock_registry.start.call_args.kwargs["session_id"] == "session-42"
    mock_registry.finish.assert_called_once()
    assert mock_registry.finish.call_args.kwargs["session_id"] == "session-42"


# ── Sub-agent history disk growth (real filesystem, not mocked) ──
#
# Every delegation mints a brand-new conversation_name, so — unlike an
# ordinary conversation — nothing else on disk ever reuses or rotates these
# files. A version of persist_subagent_history that wrote a backup and never
# pruned filled a real user's disk and made zrb unresponsive (large
# directories make every FileHistoryManager.search() call, e.g. /load's
# tab-completion, an O(n) scan). These tests exercise the *real*
# FileHistoryManager against a real directory — mocking it away, as the tests
# above do, would not have caught this.


def testpersist_subagent_history_does_not_grow_unbounded(tmp_path, monkeypatch):
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "10")

    for _ in range(200):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    subdir = tmp_path / "subagent" / "researcher"
    assert list(subdir.iterdir())
    assert len(list(subdir.iterdir())) == 10


def testpersist_subagent_history_writes_no_backup(tmp_path, monkeypatch):
    """Each conversation_name is unique and written exactly once -- a backup
    of a session that's never resaved doubles disk usage for no recovery
    value."""
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv(
        "ZRB_LLM_HISTORY_BACKUP_RETAIN", "-1"
    )  # keep-all, if any were written

    name = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    persist_subagent_history(name, [])

    assert len(list((tmp_path / "subagent" / "researcher").iterdir())) == 1
    # Nothing flat in the history root: only the subagent/ directory tree.
    assert [p for p in tmp_path.iterdir() if p.is_file()] == []


def testpersist_subagent_history_never_prunes_ordinary_conversations(
    tmp_path, monkeypatch
):
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "3")

    real_conversation = tmp_path / "my-real-conversation.json"
    real_conversation.write_text("[]")

    for _ in range(20):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    assert real_conversation.exists()
    subdir = tmp_path / "subagent" / "researcher"
    assert len(list(subdir.iterdir())) == 3


def testpersist_subagent_history_retain_minus_one_disables_pruning(
    tmp_path, monkeypatch
):
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "-1")

    for _ in range(15):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    assert len(list((tmp_path / "subagent" / "researcher").iterdir())) == 15


def testpersist_subagent_history_keeps_most_recently_written(tmp_path, monkeypatch):
    """Pruning must drop the oldest, not an arbitrary subset."""
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "2")

    names = []
    for i in range(4):
        name = format_delegated_session_name("sess1", "researcher", f"{i:08x}")
        names.append(name)
        persist_subagent_history(name, [])
        # Force distinct mtimes even on filesystems with coarse granularity.
        stamp = float(i)
        os.utime(tmp_path / "subagent" / "researcher" / f"{name}.json", (stamp, stamp))

    subdir = tmp_path / "subagent" / "researcher"
    remaining = {p.stem for p in subdir.iterdir()}
    assert remaining == {names[2], names[3]}


def testpersist_subagent_history_layout_groups_by_agent_type(tmp_path, monkeypatch):
    """Delegated transcripts land under LLM_HISTORY_DIR/subagent/<agent-type>/
    — separate from main sessions (which stay flat in the history root)."""
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "-1")

    researcher = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    reviewer = format_delegated_session_name("sess1", "code-reviewer", "e5f6a7b8")
    persist_subagent_history(researcher, [])
    persist_subagent_history(reviewer, [])

    assert (tmp_path / "subagent" / "researcher" / f"{researcher}.json").exists()
    assert (tmp_path / "subagent" / "code-reviewer" / f"{reviewer}.json").exists()
    assert not (tmp_path / f"{researcher}.json").exists()
    assert not (tmp_path / f"{reviewer}.json").exists()


def testpersist_subagent_history_never_prunes_legacy_flat_files(tmp_path, monkeypatch):
    """Old-format delegated transcripts (flat in the history root, before the
    subagent/<agent-type>/ layout) are no longer pruning candidates.

    Pruning is scoped to subagent/<agent-type>/ only: the flat root also
    holds ordinary (non-delegated) sessions, and a name that merely *looks*
    delegated there (whether a genuine pre-layout legacy file or a user
    session that happens to collide with the naming shape) must never be a
    deletion candidate. Accepted cost: legacy flat files simply accumulate
    forever now, same as before this feature existed — read/search still see
    them (`subagent_history_directories`), only pruning stops.
    """
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "2")

    legacy = format_delegated_session_name("sess1", "researcher", "a1b2c3d4")
    (tmp_path / f"{legacy}.json").write_text("[]")
    for _ in range(5):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    # The legacy flat file survives regardless of how many subagent/ writes
    # happen; the cap of 2 applies only within subagent/researcher/.
    assert (tmp_path / f"{legacy}.json").exists()
    total = len(list((tmp_path / "subagent" / "researcher").iterdir()))
    assert total == 2


def testpersist_subagent_history_never_prunes_colliding_root_session_name(
    tmp_path, monkeypatch
):
    """A user-named session sitting flat in the history root that happens to
    match the delegated naming shape (e.g. via `/save`) must never become a
    deletion candidate, regardless of how many delegated transcripts exist."""
    from zrb.llm.tool.delegate import persist_subagent_history
    from zrb.llm.util.subagent_session_naming import format_delegated_session_name

    monkeypatch.setenv("ZRB_LLM_HISTORY_DIR", str(tmp_path))
    monkeypatch.setenv("ZRB_LLM_SUBAGENT_HISTORY_RETAIN", "1")

    # Matches `parse_delegated_session`'s shape but is an ordinary user
    # session, not something `persist_subagent_history` ever wrote.
    colliding_name = "myproj-sub-reviewer-1234abcd"
    (tmp_path / f"{colliding_name}.json").write_text("[]")

    for _ in range(10):
        name = format_delegated_session_name(
            "sess1", "researcher", uuid.uuid4().hex[:8]
        )
        persist_subagent_history(name, [])

    assert (tmp_path / f"{colliding_name}.json").exists()
    assert len(list((tmp_path / "subagent" / "researcher").iterdir())) == 1


# ── Only tool-approval prompts reach main; routine sub-agent output stays
# in its own buffer (the "live sub-agent session" feature) ──


@pytest.mark.asyncio
async def test_single_delegate_does_not_flush_routine_output_to_main(
    mock_sub_agent_manager,
):
    """A sub-agent's routine buffered output (search queries, fetch status)
    must not be dumped into the main transcript on completion -- only the
    tool's own result reaches the main agent (as the tool-call return value,
    a separate mechanism from the UI transcript)."""
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    parent_ui = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    async def run_and_write_to_buffer(*args, ui=None, **kwargs):
        # Simulate the sub-agent producing routine output during its run.
        if ui is not None:
            ui.append_to_output("searching for things...")
        return "done", []

    with (
        patch("zrb.llm.tool.delegate.run_agent", side_effect=run_and_write_to_buffer),
        patch("zrb.llm.tool.delegate.get_current_ui", return_value=parent_ui),
    ):
        await tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])

    parent_ui.append_to_output.assert_not_called()


@pytest.mark.asyncio
async def test_fan_out_does_not_flush_routine_output_to_main(mock_sub_agent_manager):
    mock_sub_agent_manager.create_agent.return_value = MagicMock()
    parent_ui = MagicMock()
    tool = create_delegate_to_agent_tool(mock_sub_agent_manager)

    async def run_and_write_to_buffer(*args, ui=None, **kwargs):
        if ui is not None:
            ui.append_to_output("searching for things...")
        return "done", []

    with (
        patch("zrb.llm.tool.delegate.run_agent", side_effect=run_and_write_to_buffer),
        patch("zrb.llm.tool.delegate.get_current_ui", return_value=parent_ui),
    ):
        await tool(
            tasks=[
                {
                    "agent_name": "test-agent",
                    "deliverable": "d",
                    "task": "t",
                    "non_goals": [],
                }
            ]
        )

    parent_ui.append_to_output.assert_not_called()

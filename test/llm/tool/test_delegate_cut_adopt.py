"""A send-now key moves a running delegation aside instead of holding the turn.

A steered message is read at the next model request, and the next request is
assembled only after the running tool call returns. A synchronous
`DelegateToAgent` that runs for an hour therefore makes the assistant
unreachable for an hour. These tests pin the way out: the sub-agent steps aside
into the background registry under a handle, the tool call returns while the
work keeps going, and `GetDelegationResult` collects it later.
"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.shell_cut import ShellCutSignal, current_shell_cut_signal
from zrb.llm.subagent.live_session import live_subagent_session_registry
from zrb.llm.subagent.manager import SubAgentDefinition, SubAgentManager
from zrb.llm.tool.delegate import create_delegate_to_agent_tool
from zrb.llm.tool.delegate_background import (
    create_get_delegation_result_tool,
    get_background_registry,
)

RUN_AGENT = "zrb.llm.tool.delegate.run_agent"


@pytest.fixture
def manager():
    sub_agent_manager = MagicMock(spec=SubAgentManager)
    sub_agent_manager.create_agent.return_value = MagicMock()
    sub_agent_manager.scan.return_value = [
        SubAgentDefinition(
            name="test-agent",
            path="path",
            description="A test agent",
            system_prompt="prompt",
        )
    ]
    return sub_agent_manager


@pytest.fixture(autouse=True)
def clean_delegation_state():
    """An adopted task outlives the test that moved it: nothing may leak."""
    yield
    get_background_registry().cancel_all()
    live_subagent_session_registry.clear()


def _handles(text: str) -> list[str]:
    """Every delegation handle the report offers, in the order it offers them."""
    return list(
        dict.fromkeys(re.findall(r"GetDelegationResult\(handle='([^']+)'\)", text))
    )


def _gated_run_agent(
    started: asyncio.Event, release: asyncio.Event, answer: str = "the answer"
) -> Callable[..., Awaitable[tuple[str, list]]]:
    """A `run_agent` stand-in that reports it started, then waits for *release*."""

    async def run_agent(**kwargs) -> tuple[str, list]:
        started.set()
        await release.wait()
        return answer, []

    return run_agent


async def _run_with_cut(
    call: Callable[[], Awaitable[str]], started: asyncio.Event
) -> str:
    """Run *call* under a cut signal fired once the sub-agent has started."""
    signal = ShellCutSignal()
    token = current_shell_cut_signal.set(signal)
    try:
        running = asyncio.ensure_future(call())
        await started.wait()
        signal.cut()
        return await asyncio.wait_for(running, 20)
    finally:
        current_shell_cut_signal.reset(token)


@pytest.mark.asyncio
async def test_a_cut_moves_the_running_delegation_to_the_background(manager):
    started, release = asyncio.Event(), asyncio.Event()
    tool = create_delegate_to_agent_tool(manager)
    with patch(RUN_AGENT, side_effect=_gated_run_agent(started, release)):
        message = await _run_with_cut(
            lambda: tool(
                agent_name="test-agent", deliverable="d", task="t", non_goals=[]
            ),
            started,
        )
        [handle] = _handles(message)
        # The work was not thrown away: it is still running, under that handle.
        still_running = await create_get_delegation_result_tool()(handle)
        assert "still running" in still_running.lower()

        release.set()
        collected = await asyncio.wait_for(
            create_get_delegation_result_tool()(handle, wait=5), 20
        )

    assert "the answer" in collected


@pytest.mark.asyncio
async def test_the_report_says_the_turn_needs_the_delegation_out_of_the_way(manager):
    started, release = asyncio.Event(), asyncio.Event()
    tool = create_delegate_to_agent_tool(manager)
    with patch(RUN_AGENT, side_effect=_gated_run_agent(started, release)):
        message = await _run_with_cut(
            lambda: tool(
                agent_name="test-agent", deliverable="d", task="t", non_goals=[]
            ),
            started,
        )

    [handle] = _handles(message)
    assert f"Handle: {handle}" in message
    assert "Error" not in message, "the model must not read this as a failure"
    assert "NOT cancelled" in message
    assert "message" in message, "the model is not told why it was moved"
    assert f"GetDelegationResult(handle='{handle}')" in message
    assert "Do not delegate the same work again" in message


@pytest.mark.asyncio
async def test_a_cut_from_before_the_call_does_not_move_it(manager):
    """The key was pressed during an earlier tool call; this delegation was not
    running then and must be left alone."""
    tool = create_delegate_to_agent_tool(manager)
    signal = ShellCutSignal()
    signal.cut()
    token = current_shell_cut_signal.set(signal)
    try:
        with patch(RUN_AGENT, new_callable=AsyncMock) as run_agent:
            run_agent.return_value = ("quick answer", [])
            message = await tool(
                agent_name="test-agent", deliverable="d", task="t", non_goals=[]
            )
    finally:
        current_shell_cut_signal.reset(token)

    assert "quick answer" in message
    assert _handles(message) == []


@pytest.mark.asyncio
async def test_no_signal_waits_for_the_delegation_as_before(manager):
    """Outside a run there is nobody to cut in: the tool holds the turn."""
    tool = create_delegate_to_agent_tool(manager)
    with patch(RUN_AGENT, new_callable=AsyncMock) as run_agent:
        run_agent.return_value = ("quick answer", [])
        message = await tool(
            agent_name="test-agent", deliverable="d", task="t", non_goals=[]
        )

    assert "completed:" in message
    assert "quick answer" in message
    assert _handles(message) == []


@pytest.mark.asyncio
async def test_a_cancelled_turn_does_not_cancel_the_adopted_delegation(manager):
    """Send-now steers the turn when it can and cancels it when it cannot.

    Once the delegation has moved, the turn's own frame may be cancelled under
    it. The adopted task must survive that: an `asyncio.Task` nobody awaits is
    not part of the cancelled frame, but a task owned by a cancelled `gather`
    would be, and the work would be lost.
    """
    started, release, adopted = asyncio.Event(), asyncio.Event(), asyncio.Event()
    report: dict[str, str] = {}
    tool = create_delegate_to_agent_tool(manager)

    async def the_turn() -> None:
        report["message"] = await tool(
            agent_name="test-agent", deliverable="d", task="t", non_goals=[]
        )
        adopted.set()
        await asyncio.Event().wait()  # the rest of the turn

    signal = ShellCutSignal()
    token = current_shell_cut_signal.set(signal)
    try:
        with patch(RUN_AGENT, side_effect=_gated_run_agent(started, release)):
            frame = asyncio.ensure_future(the_turn())
            await started.wait()
            signal.cut()
            await adopted.wait()
            frame.cancel()
            with pytest.raises(asyncio.CancelledError):
                await frame
    finally:
        current_shell_cut_signal.reset(token)

    [handle] = _handles(report["message"])
    release.set()
    collected = await asyncio.wait_for(
        create_get_delegation_result_tool()(handle, wait=5), 20
    )
    assert "the answer" in collected


@pytest.mark.asyncio
async def test_a_cancelled_turn_stops_a_delegation_that_never_moved(manager):
    """A delegation still inside its turn stops with it.

    The cancel below arrives without a cut, so nothing adopted the run: the turn
    that would have reported the result is gone, and a sub-agent left running
    would work unwatched, with nobody left to read what it produced.
    """
    started, stopped = asyncio.Event(), asyncio.Event()

    async def blocking_run_agent(**kwargs) -> "tuple[str, list]":
        """Never answers: only a cancel ends it, which is what the test asserts."""
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            stopped.set()
            raise
        raise AssertionError("released without a cancel")

    tool = create_delegate_to_agent_tool(manager)
    with patch(RUN_AGENT, side_effect=blocking_run_agent):
        frame = asyncio.ensure_future(
            tool(agent_name="test-agent", deliverable="d", task="t", non_goals=[])
        )
        await started.wait()
        frame.cancel()
        with pytest.raises(asyncio.CancelledError):
            await frame
        await asyncio.wait_for(stopped.wait(), 20)

    assert stopped.is_set()


def _fan_out_spec(label: str) -> dict:
    return {
        "agent_name": "test-agent",
        "deliverable": label,
        "task": label,
        "non_goals": [],
    }


@pytest.mark.asyncio
async def test_a_cut_moves_every_in_flight_sibling_aside(manager):
    """A fan-out is several delegations holding the same turn: all of them move."""
    labels = ("alpha", "beta", "gamma")
    started, release = asyncio.Event(), asyncio.Event()
    in_flight: set[str] = set()

    async def tracking_run_agent(**kwargs) -> tuple[str, list]:
        label = kwargs["message"].split("DELIVERABLE: ")[1].split("\n")[0]
        in_flight.add(label)
        if in_flight == set(labels):
            started.set()
        await release.wait()
        return f"answer for {label}", []

    tool = create_delegate_to_agent_tool(manager)
    with patch(RUN_AGENT, side_effect=tracking_run_agent):
        message = await _run_with_cut(
            lambda: tool(tasks=[_fan_out_spec(label) for label in labels]), started
        )
        handles = _handles(message)
        assert len(handles) == 3, message

        release.set()
        collected = [
            await asyncio.wait_for(
                create_get_delegation_result_tool()(handle, wait=5), 20
            )
            for handle in handles
        ]

    assert "Error" not in message
    for label in labels:
        assert any(f"answer for {label}" in text for text in collected), (
            label,
            collected,
        )


@pytest.mark.asyncio
async def test_a_fan_out_without_a_cut_reports_every_result_as_before(manager):
    """Nothing moved, so the combined report is the one the turn always gave."""
    tool = create_delegate_to_agent_tool(manager)
    with patch(RUN_AGENT, new_callable=AsyncMock) as run_agent:
        run_agent.side_effect = [("Result A", []), ("Result B", [])]
        message = await tool(
            tasks=[_fan_out_spec("alpha"), _fan_out_spec("beta")],
        )

    assert message.count("completed:") == 2
    assert "Result A" in message and "Result B" in message
    assert _handles(message) == []


@pytest.mark.asyncio
async def test_a_cancelled_fan_out_stops_every_sibling_that_never_moved(manager):
    """One cancel reaches every sibling, the way one `gather` used to."""
    in_flight: set[str] = set()
    started, stopped = asyncio.Event(), asyncio.Event()

    async def blocking_run_agent(**kwargs) -> "tuple[str, list]":
        label = kwargs["message"].split("DELIVERABLE: ")[1].split("\n")[0]
        in_flight.add(label)
        if len(in_flight) == 2:
            started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            in_flight.discard(label)
            if not in_flight:
                stopped.set()
            raise
        raise AssertionError("released without a cancel")

    tool = create_delegate_to_agent_tool(manager)
    with patch(RUN_AGENT, side_effect=blocking_run_agent):
        frame = asyncio.ensure_future(
            tool(tasks=[_fan_out_spec("alpha"), _fan_out_spec("beta")])
        )
        await started.wait()
        frame.cancel()
        with pytest.raises(asyncio.CancelledError):
            await frame
        await asyncio.wait_for(stopped.wait(), 20)

    assert not in_flight


@pytest.mark.asyncio
async def test_another_sessions_teardown_leaves_an_adopted_delegation_running(manager):
    """A handle belongs to the session that minted it.

    The registry is process-wide; the work in it is not. Another chat session
    ending in the same process cancels only its own delegations, so this
    session's handle still collects — and does not answer "Unknown handle".
    """
    started, release = asyncio.Event(), asyncio.Event()
    tool = create_delegate_to_agent_tool(manager)
    with patch(RUN_AGENT, side_effect=_gated_run_agent(started, release)):
        message = await _run_with_cut(
            lambda: tool(
                agent_name="test-agent", deliverable="d", task="t", non_goals=[]
            ),
            started,
        )
        [handle] = _handles(message)

        get_background_registry().cancel_all("some-other-session")
        still_running = await create_get_delegation_result_tool()(handle)
        assert "still running" in still_running.lower()

        release.set()
        collected = await asyncio.wait_for(
            create_get_delegation_result_tool()(handle, wait=5), 20
        )

    assert "the answer" in collected


@pytest.mark.asyncio
async def test_a_sibling_that_raises_still_reports_its_own_error(manager):
    """A delegation that blows up outside its run fails alone.

    `enter_worktree` runs before the run's own try, so a git failure there ends
    that task with an exception. The other sibling must still report its result.
    """
    tool = create_delegate_to_agent_tool(manager)
    isolated = dict(_fan_out_spec("alpha"), isolate_worktree=True)
    with (
        patch(RUN_AGENT, new_callable=AsyncMock) as run_agent,
        patch(
            "zrb.llm.tool.delegate.current_head_sha",
            new_callable=AsyncMock,
            return_value="base123",
        ),
        patch(
            "zrb.llm.tool.delegate.enter_worktree",
            side_effect=RuntimeError("no worktree"),
        ),
    ):
        run_agent.return_value = ("Result B", [])
        message = await tool(tasks=[isolated, _fan_out_spec("beta")])

    assert "Error: no worktree" in message
    assert "Result B" in message

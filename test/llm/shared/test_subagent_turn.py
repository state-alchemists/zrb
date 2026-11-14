"""The one sub-agent turn: what it hands the engine, and what it never drops.

The delegate tool and a live-session continuation used to make this call each on
their own, and drifted apart one argument at a time — a different limiter, a
different way of passing `yolo`, and a captured grant one of them honoured and
the other never had. These tests read the single call that replaced both, so the
drift cannot come back unnoticed.
"""

import pytest

from zrb.llm.agent.run.authority_snapshot import AuthoritySnapshot
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.shared.agent_state import (
    current_approval_channel,
    current_tool_confirmation,
    get_current_approval_channel,
    get_current_tool_confirmation,
)
from zrb.llm.shared.subagent_turn import SubAgentTurn, run_subagent_turn
from zrb.llm.shared.usage_log import COMPONENT_SUBAGENT, current_component
from zrb.util.contextvar_scope import scoped

APPROVAL_HANDLER = object()
APPROVAL_CHANNEL = object()
AMBIENT_HANDLER = object()
AMBIENT_CHANNEL = object()


@pytest.fixture
def captured():
    """The grant a delayed continuation resumes under."""
    return AuthoritySnapshot(
        permission_policy=object(),
        yolo=True,
        sandbox_policy=object(),
        hook_manager=object(),
        tool_confirmation=APPROVAL_HANDLER,
        approval_channel=APPROVAL_CHANNEL,
    )


def _turn(**overrides) -> SubAgentTurn:
    fields = dict(
        agent=object(),
        message="do the thing",
        ui=object(),
        run_scope="scope-1",
        limiter=LLMLimiter(),
    )
    fields.update(overrides)
    return SubAgentTurn(**fields)


async def _capture(monkeypatch, **turn_fields) -> dict:
    """Run one turn with the engine mocked; return the arguments it received."""
    seen: dict = {}

    async def fake_run_agent(**kwargs):
        seen.update(kwargs)
        seen["component"] = current_component()
        seen["approval_channel"] = get_current_approval_channel()
        seen["tool_confirmation"] = get_current_tool_confirmation()
        return "the answer", [{"turn": 1}]

    monkeypatch.setattr(
        "zrb.llm.shared.subagent_turn.run_agent", fake_run_agent
    )
    turn = _turn(**turn_fields)
    result, history = await run_subagent_turn(turn)
    seen["result"] = result
    seen["history"] = history
    seen["turn"] = turn
    return seen


@pytest.mark.asyncio
async def test_the_turn_is_attributed_to_the_sub_agent(monkeypatch):
    """Its rounds are the sub-agent's spend, not the parent conversation's."""
    seen = await _capture(monkeypatch)
    assert seen["component"] == COMPONENT_SUBAGENT


@pytest.mark.asyncio
async def test_the_turn_hands_the_run_what_the_caller_gave_it(monkeypatch):
    """Every input reaches the engine unchanged — no re-derivation in between."""
    seen = await _capture(monkeypatch, nested=True, history=[{"old": 1}])
    turn = seen["turn"]
    assert seen["agent"] is turn.agent
    assert seen["message"] == "do the thing"
    assert seen["ui"] is turn.ui
    assert seen["run_scope"] == "scope-1"
    assert seen["limiter"] is turn.limiter
    assert seen["message_history"] == [{"old": 1}]
    assert seen["nested"] is True
    assert seen["result"] == "the answer"
    assert seen["history"] == [{"turn": 1}]


@pytest.mark.asyncio
async def test_a_captured_grant_reaches_the_run(monkeypatch, captured):
    """A continuation runs under what the delegation was granted, not ambient."""
    seen = await _capture(monkeypatch, authority=captured)
    assert seen["permission_policy"] is captured.permission_policy
    assert seen["sandbox_policy"] is captured.sandbox_policy
    assert seen["hook_manager"] is captured.hook_manager
    assert seen["tool_confirmation"] is captured.tool_confirmation
    assert seen["approval_channel"] is captured.approval_channel


@pytest.mark.asyncio
async def test_a_captured_approval_is_bound_not_only_passed(monkeypatch, captured):
    """`run_agent` reads a `None` argument as "inherit", so the capture is bound.

    Passing the handler and channel is not enough: a delegation captured with
    none would pick up whatever a later turn leaves bound.
    """
    seen = await _capture(monkeypatch, authority=captured)
    assert seen["tool_confirmation"] is APPROVAL_HANDLER
    assert seen["approval_channel"] is APPROVAL_CHANNEL


@pytest.mark.asyncio
async def test_without_a_capture_the_ambient_approval_survives(monkeypatch):
    """A turn started inside its parent's run keeps the handler already bound."""
    with (
        scoped(current_tool_confirmation, AMBIENT_HANDLER),
        scoped(current_approval_channel, AMBIENT_CHANNEL),
    ):
        seen = await _capture(monkeypatch)
    assert seen["tool_confirmation"] is AMBIENT_HANDLER
    assert seen["approval_channel"] is AMBIENT_CHANNEL


@pytest.mark.asyncio
async def test_the_callers_yolo_wins_over_the_captured_one(monkeypatch, captured):
    """A delegation tool's per-call `yolo` is a decision made after the capture."""
    seen = await _capture(monkeypatch, authority=captured, yolo=False)
    assert seen["yolo"] is False


@pytest.mark.asyncio
async def test_the_captured_yolo_applies_when_the_caller_names_none(monkeypatch, captured):
    """`None` means "inherit", and for a delayed turn the grant is what to inherit."""
    seen = await _capture(monkeypatch, authority=captured)
    assert seen["yolo"] is True


@pytest.mark.asyncio
async def test_with_neither_the_run_inherits_the_ambient_yolo(monkeypatch):
    """An untargeted turn leaves the decision to the engine, as `run_agent` does."""
    seen = await _capture(monkeypatch)
    assert seen["yolo"] is None

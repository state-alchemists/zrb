"""A default-approved tool runs without asking, and a rule still wins.

The stage sits below the permission policy on purpose: it removes a prompt
nobody wanted, never a decision somebody made. These pin both halves.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.agent.run.deferred_calls import process_deferred_requests
from zrb.llm.agent.run.hook_result_extractor import PreToolDecision
from zrb.llm.hook.manager import HookManager
from zrb.llm.permission import ASK
from zrb.llm.ui.any_ui import AnyUI


class _Approved:
    """Stands in for pydantic-ai's ``ToolApproved``."""


class _Denied:
    def __init__(self, message):
        self.message = message


class _Results:
    def __init__(self, calls=None, approvals=None, metadata=None):
        self.calls = calls if calls is not None else {}
        self.approvals = approvals if approvals is not None else {}
        self.metadata = metadata


@pytest.fixture(autouse=True)
def _framework_types():
    with (
        patch("pydantic_ai.DeferredToolResults", _Results),
        patch("pydantic_ai.ToolApproved", _Approved),
        patch("pydantic_ai.ToolDenied", _Denied),
    ):
        yield


def _call(tool_name="Remember", args=None):
    call = MagicMock()
    call.tool_name = tool_name
    call.args = {"id": "probe-claim"} if args is None else args
    call.tool_call_id = "call_1"
    return call


def _hook_manager():
    manager = MagicMock(spec=HookManager)
    manager.execute_hooks = AsyncMock(return_value=[])
    return manager


async def _approval(call, policy=None, pre_tool=None):
    """The verdict the cascade reached for *call*."""
    result_output = MagicMock()
    result_output.calls = [call]
    result_output.approvals = []
    with (
        patch("zrb.llm.permission.get_effective_policy", return_value=policy),
        patch("zrb.llm.permission.tool_capability", return_value="cap"),
        patch(
            "zrb.llm.agent.run.deferred_calls.extract_pre_tool_decision",
            return_value=pre_tool or PreToolDecision(),
        ),
    ):
        results = await process_deferred_requests(
            result_output, None, MagicMock(spec=AnyUI), _hook_manager()
        )
    return results.approvals["call_1"]


def _registered(value: bool):
    return patch(
        "zrb.llm.agent.run.deferred_calls.is_default_auto_approve",
        return_value=value,
    )


def _asking_policy():
    policy = MagicMock()
    policy.decide.return_value = ASK
    return policy


@pytest.mark.asyncio
async def test_a_default_approved_tool_runs_without_asking():
    with _registered(True):
        verdict = await _approval(_call())
    assert isinstance(verdict, _Approved)


@pytest.mark.asyncio
async def test_a_tool_outside_the_registry_still_asks():
    with _registered(False):
        verdict = await _approval(_call())
    assert not isinstance(verdict, _Approved)


@pytest.mark.asyncio
async def test_a_permission_rule_that_asks_still_wins():
    """The whole reason this sits below the ruleset: `ask` stays a hard ask."""
    with _registered(True):
        verdict = await _approval(_call(), policy=_asking_policy())
    assert isinstance(verdict, _Denied)


@pytest.mark.asyncio
async def test_a_pre_tool_use_ask_still_wins():
    with _registered(True):
        verdict = await _approval(_call(), pre_tool=PreToolDecision(force_prompt=True))
    assert isinstance(verdict, _Denied)


@pytest.mark.asyncio
async def test_an_escape_from_the_sandbox_still_asks():
    """However ordinary the tool is, leaving the sandbox is a request for a human."""
    call = _call(args={"id": "probe-claim", "dangerously_skip_sandbox": True})
    with _registered(True):
        verdict = await _approval(call)
    assert not isinstance(verdict, _Approved)

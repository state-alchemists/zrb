"""The approval fall-through must produce a verdict pydantic-ai accepts.

The other tests in this directory replace `pydantic_ai.DeferredToolResults`
with a stand-in, where a stored `None` looked harmless. The real class rejects
it in `to_tool_call_results()` with a `UserError`, so the resumed turn dies and
the pending call is lost. This module deliberately uses the real objects.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import DeferredToolRequests, DeferredToolResults, ToolDenied
from pydantic_ai.messages import ToolCallPart

from zrb.llm.capabilities.hook.manager import HookManager
from zrb.llm.engine.agent.run.deferred_calls import process_deferred_requests


@pytest.mark.asyncio
async def test_a_call_with_no_approval_mechanism_stores_a_real_verdict():
    """No channel, no confirmation, no policy opinion: nobody answered the
    call, so it is denied — and the stored verdict survives the round trip."""
    call = ToolCallPart(
        tool_name="test_tool", args={"path": "a.txt"}, tool_call_id="call_fallthrough"
    )
    hook_manager = MagicMock(spec=HookManager)
    hook_manager.execute_hooks = AsyncMock(return_value=[])

    with (
        patch(
            "zrb.llm.capabilities.permission.get_effective_policy", return_value=None
        ),
        patch(
            "zrb.llm.engine.agent.run.deferred_calls.get_interactive_mode",
            return_value=True,
        ),
        patch(
            "zrb.llm.contracts.shared.agent_state.get_current_yolo", return_value=None
        ),
    ):
        result = await process_deferred_requests(
            DeferredToolRequests(calls=[call]), None, MagicMock(), hook_manager
        )

    assert result is not None
    verdict = result.approvals["call_fallthrough"]
    assert isinstance(verdict, ToolDenied)
    assert "no approval mechanism" in verdict.message
    # Regression: a `None` here raised `UserError: Invalid approval result` and
    # lost the call instead of resuming the turn with a denial.
    converted = DeferredToolResults(approvals=result.approvals).to_tool_call_results()
    assert converted == {"call_fallthrough": verdict}

"""Three calls the cascade used to answer by itself.

A capability-keyed `ask` is a hard ask (ADR-0062), the sandbox escape hatch is
never auto-approved (ADR-0065, `docs/llm/sandbox.md`), and the MCP loader starts
every server its config names — so a write to that config is a human's call. All
three were approved with nobody asked.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai import ToolApproved, ToolDenied

from zrb.llm.capabilities.permission import Capability, resolve_policy
from zrb.llm.engine.agent.run.deferred_calls import _resolve_approval
from zrb.llm.engine.agent.run.tool_capabilities import register_tool_capabilities
from zrb.llm.engine.agent.types import ToolCallPart


def _a_human():
    """A confirmation stand-in: records being asked, then denies."""
    asked: list[str] = []

    def confirm(call):
        asked.append(call.tool_name)
        return ToolDenied("a human was asked")

    return asked, confirm


@pytest.mark.asyncio
async def test_the_sandbox_escape_flag_is_not_approved_under_yolo():
    """`cat ~/.ssh/id_rsa` with `dangerously_skip_sandbox`, under YOLO.

    YOLO approved it without asking: the stage below it refused a sandbox
    escape, and this one could not see the arguments to notice.
    """
    call = ToolCallPart(
        tool_name="Shell",
        args={"command": "cat ~/.ssh/id_rsa", "dangerously_skip_sandbox": True},
        tool_call_id="call_escape",
    )
    asked, confirm = _a_human()
    with (
        patch(
            "zrb.llm.capabilities.permission.get_effective_policy", return_value=None
        ),
        patch(
            "zrb.llm.contracts.shared.agent_state.get_current_yolo", return_value=True
        ),
    ):
        verdict = await _resolve_approval(call, MagicMock(), confirm, None, None)
    assert not isinstance(verdict, ToolApproved)
    assert asked == ["Shell"]


@pytest.mark.asyncio
async def test_a_capability_keyed_ask_still_asks_after_deferral():
    """`edit:ask` used to be invisible to the cascade.

    A deferred part carries no capability tag, so asking the part answered
    `UNKNOWN` and the write matched the later `*:allow` instead.
    """
    register_tool_capabilities({"Write": Capability.EDIT})
    call = ToolCallPart(
        tool_name="Write", args={"path": "notes.txt"}, tool_call_id="call_edit"
    )
    asked, confirm = _a_human()
    with (
        patch(
            "zrb.llm.capabilities.permission.get_effective_policy",
            return_value=resolve_policy("read:allow,edit:ask,*:allow"),
        ),
        patch(
            "zrb.llm.engine.agent.run.deferred_calls.get_interactive_mode",
            return_value=True,
        ),
    ):
        verdict = await _resolve_approval(call, MagicMock(), confirm, None, None)
    assert not isinstance(verdict, ToolApproved)
    assert asked == ["Write"]


@pytest.mark.asyncio
async def test_a_write_to_the_mcp_config_asks_even_under_yolo(tmp_path, monkeypatch):
    """The loader starts every server the file names, so editing it is a human's
    decision — the one ASK that outranks YOLO (ADR-0062)."""
    monkeypatch.chdir(tmp_path)
    register_tool_capabilities({"Write": Capability.EDIT})
    call = ToolCallPart(
        tool_name="Write",
        args={"path": str(tmp_path / "mcp-config.json")},
        tool_call_id="call_mcp_config",
    )
    asked, confirm = _a_human()
    with (
        patch(
            "zrb.llm.capabilities.permission.get_effective_policy", return_value=None
        ),
        patch(
            "zrb.llm.engine.agent.run.deferred_calls.get_interactive_mode",
            return_value=True,
        ),
        patch(
            "zrb.llm.contracts.shared.agent_state.get_current_yolo", return_value=True
        ),
    ):
        verdict = await _resolve_approval(call, MagicMock(), confirm, None, None)
    assert not isinstance(verdict, ToolApproved)
    assert asked == ["Write"]

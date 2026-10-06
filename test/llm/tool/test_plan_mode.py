"""Tests for plan mode: the tools, the gate's read-only enforcement, and the
system-context mode line."""

import pytest

from zrb.llm.permission import Capability, tag
from zrb.llm.permission.state import (
    AgentMode,
    AgentModeState,
    current_agent_mode,
    get_current_agent_mode,
)
from zrb.llm.tool.plan_mode import enter_plan_mode, exit_plan_mode


@pytest.fixture(autouse=True)
def reset_mode():
    token = current_agent_mode.set(AgentModeState(mode=AgentMode.BUILD))
    yield
    current_agent_mode.reset(token)


@pytest.mark.asyncio
async def test_enter_plan_mode_sets_mode():
    msg = await enter_plan_mode(reason="investigating")
    assert get_current_agent_mode() == AgentMode.PLAN
    assert "PLAN mode" in msg
    assert "investigating" in msg


@pytest.mark.asyncio
async def test_exit_plan_mode_clears_mode_and_echoes_plan():
    await enter_plan_mode()
    msg = await exit_plan_mode(plan="1. do X\n2. do Y")
    assert get_current_agent_mode() == AgentMode.BUILD
    assert "do X" in msg


def test_plan_mode_tools_are_meta():
    assert Capability.META.value == "meta"
    from zrb.llm.permission import tool_capability

    assert tool_capability(enter_plan_mode) == Capability.META
    assert tool_capability(exit_plan_mode) == Capability.META


@pytest.mark.asyncio
async def test_plan_mode_blocks_edit_and_execute_allows_read():
    """Under plan mode, the gate denies edit/execute/delegate, allows read."""
    from zrb.llm.agent.common import create_safe_wrapper

    ran = []

    def write_file(path: str = ""):
        ran.append(("write", path))
        return "wrote"

    def read_file(path: str = ""):
        ran.append(("read", path))
        return "contents"

    def run_shell(command: str = ""):
        ran.append(("shell", command))
        return "out"

    tag(write_file, Capability.EDIT)
    tag(read_file, Capability.READ)
    tag(run_shell, Capability.EXECUTE)

    w_write = create_safe_wrapper(write_file)
    w_read = create_safe_wrapper(read_file)
    w_shell = create_safe_wrapper(run_shell)

    await enter_plan_mode()

    r_write = await w_write(path="a.py")
    r_shell = await w_shell(command="ls")
    r_read = await w_read(path="a.py")

    assert r_write.metadata.get("blocked") is True
    assert r_shell.metadata.get("blocked") is True
    assert r_read.return_value == "contents"
    assert ("write", "a.py") not in ran
    assert ("shell", "ls") not in ran
    assert ("read", "a.py") in ran


@pytest.mark.asyncio
async def test_plan_mode_allows_read_through_full_toolset_dispatch():
    """The outer ``SafeToolsetWrapper.call_tool`` gate resolves capability from
    ``ToolDefinition.metadata``, so plan mode allows Read through the real
    ``wrap_tool`` + ``FunctionToolset`` + ``wrap_toolset`` chain."""
    from unittest.mock import MagicMock

    from pydantic_ai.tools import RunContext
    from pydantic_ai.toolsets import FunctionToolset
    from pydantic_ai.usage import RunUsage

    from zrb.llm.agent.common import wrap_tool, wrap_toolset

    def read_file(path: str = ""):
        return f"contents of {path}"

    def write_file(path: str = ""):
        return "wrote"

    tag(read_file, Capability.READ)
    tag(write_file, Capability.EDIT)

    toolset = wrap_toolset(
        FunctionToolset(tools=[wrap_tool(read_file), wrap_tool(write_file)])
    )
    ctx = RunContext(deps=None, model=MagicMock(), usage=RunUsage())
    tools = await toolset.get_tools(ctx)

    await enter_plan_mode()
    try:
        read_result = await toolset.call_tool(
            "read_file", {"path": "a.py"}, ctx, tools["read_file"]
        )
        write_result = await toolset.call_tool(
            "write_file", {"path": "a.py"}, ctx, tools["write_file"]
        )
    finally:
        await exit_plan_mode(plan="done")

    assert read_result.return_value == "contents of a.py"
    assert write_result.metadata.get("blocked") is True


@pytest.mark.asyncio
async def test_exit_plan_mode_requires_approval_even_with_yolo():
    """Verify that YOLO=True cannot auto-approve ExitPlanMode in plan mode."""
    from zrb.llm.permission import ASK, get_effective_policy

    await enter_plan_mode()
    try:
        policy = get_effective_policy()
        assert policy.decide("ExitPlanMode", Capability.META, {}) == ASK
    finally:
        await exit_plan_mode(plan="done")

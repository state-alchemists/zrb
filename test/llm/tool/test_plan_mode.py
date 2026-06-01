"""Tests for plan mode: the tools, the gate's read-only enforcement, and the
system-context mode line."""

import pytest

from zrb.llm.permission import Capability, tag
from zrb.llm.permission.state import (
    AgentMode,
    current_agent_mode,
    get_current_agent_mode,
)
from zrb.llm.tool.plan_mode import enter_plan_mode, exit_plan_mode


@pytest.fixture(autouse=True)
def reset_mode():
    token = current_agent_mode.set(AgentMode.DEFAULT)
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
    assert get_current_agent_mode() == AgentMode.DEFAULT
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
    assert r_read.content == "contents"
    assert ("write", "a.py") not in ran
    assert ("shell", "ls") not in ran
    assert ("read", "a.py") in ran


@pytest.mark.asyncio
async def test_plan_mode_allows_meta_tools():
    """Meta tools (incl. ExitPlanMode itself) are never blocked in plan mode."""
    from zrb.llm.agent.common import create_safe_wrapper

    def todo(content: str = ""):
        return "noted"

    tag(todo, Capability.META)
    wrapped = create_safe_wrapper(todo)

    await enter_plan_mode()
    result = await wrapped(content="x")
    assert result.content == "noted"
    assert "blocked" not in result.metadata

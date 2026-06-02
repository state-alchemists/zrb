"""Tests for background shell command execution."""

import asyncio
from unittest.mock import patch

import pytest

from zrb.llm.permission import Capability, tool_capability
from zrb.llm.tool.shell_background import (
    create_monitor_process_tool,
    create_shell_background_tool,
    get_shell_background_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    yield
    get_shell_background_registry().cancel_all()


def test_capabilities():
    assert tool_capability(create_shell_background_tool()) == Capability.EXECUTE
    assert tool_capability(create_monitor_process_tool()) == Capability.EXECUTE


def test_tool_names():
    assert create_shell_background_tool().__name__ == "ShellBackground"
    assert create_monitor_process_tool().__name__ == "MonitorProcess"


@pytest.mark.asyncio
async def test_shell_background_returns_handle(tmp_path):
    tool = create_shell_background_tool()
    msg = await tool("echo hello", "greeting", str(tmp_path))
    assert "Handle:" in msg
    # Extract handle for cleanup
    handle = msg.split("Handle:")[1].split(".")[0].strip()
    registry = get_shell_background_registry()
    # Let it finish
    import time

    await asyncio.sleep(0.5)
    result = registry.poll(handle)
    assert "hello" in result or "exited" in result or "running" in result


@pytest.mark.asyncio
async def test_monitor_process_unknown():
    tool = create_monitor_process_tool()
    msg = await tool("nonexistent-handle")
    assert "Unknown handle" in msg


@pytest.mark.asyncio
async def test_monitor_process_kill(tmp_path):
    tool = create_shell_background_tool()
    msg = await tool("sleep 30", "sleeper", str(tmp_path))
    handle = msg.split("Handle:")[1].split(".")[0].strip()

    monitor = create_monitor_process_tool()
    result = await monitor(handle, kill=True)
    assert "Killed" in result
    # Poll again — handle is consumed after kill
    result2 = await monitor(handle)
    assert "Unknown handle" in result2


@pytest.mark.asyncio
async def test_cancel_all_clears(tmp_path):
    tool = create_shell_background_tool()
    msg = await tool("sleep 30", "", str(tmp_path))
    handle = msg.split("Handle:")[1].split(".")[0].strip()

    registry = get_shell_background_registry()
    registry.cancel_all()

    monitor = create_monitor_process_tool()
    result = await monitor(handle)
    assert "Unknown handle" in result

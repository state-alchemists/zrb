import json
import os
import tempfile
from unittest.mock import patch

import pytest
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from zrb.llm.tool.mcp import load_mcp_config


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
    with patch("os.path.expanduser", return_value=home_dir), patch(
        "os.getcwd", return_value=sub_dir
    ):

        toolsets = load_mcp_config()

        assert len(toolsets) == 2
        assert all(isinstance(t, MCPToolset) for t in toolsets)

        by_id = {t.id: t for t in toolsets}
        assert set(by_id) == {"stdio_server", "sse_server"}

        # Stdio: transport is a StdioTransport built from command/args/env
        stdio_transport = by_id["stdio_server"].client.transport
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

    with patch("os.path.expanduser", return_value=home_dir), patch(
        "os.getcwd", return_value=sub_dir
    ):

        toolsets = load_mcp_config()

        assert len(toolsets) == 1
        assert isinstance(toolsets[0], MCPToolset)
        transport = toolsets[0].client.transport
        assert isinstance(transport, StdioTransport)
        assert transport.command == "cmd2"

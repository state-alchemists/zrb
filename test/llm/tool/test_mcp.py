import json
import os
import tempfile
from unittest.mock import patch

import pytest
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from zrb.config.config import CFG
from zrb.llm.tool.mcp import cap_mcp_result, load_mcp_config


def test_cap_mcp_result_truncates_long_string():
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}):
        out = cap_mcp_result("x" * 5000)
    assert isinstance(out, str)
    assert "[TRUNCATED]" in out
    assert len(out) < 600


def test_cap_mcp_result_passes_small_structured_through():
    data = {"a": 1, "b": [1, 2, 3]}
    # Small structured results keep their type so the model can consume them.
    assert cap_mcp_result(data) is data


def test_cap_mcp_result_caps_oversized_structured():
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}):
        out = cap_mcp_result({"big": "y" * 5000})
    assert isinstance(out, str)
    assert "[TRUNCATED]" in out
    assert len(out) < 600


def test_cap_mcp_result_passes_binary_through_intact():
    """A large image must never be stringified into a truncated repr.

    Regression: capping via str(result) turned MCP screenshot results into
    "BinaryContent(data=b'\\x89PNG..." head text, losing the image entirely.
    """
    from pydantic_ai.messages import BinaryContent

    image = BinaryContent(data=b"\x89PNG" * 100_000, media_type="image/png")
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}):
        assert cap_mcp_result(image) is image


def test_cap_mcp_result_caps_text_items_but_keeps_binary_in_list():
    from pydantic_ai.messages import BinaryContent

    image = BinaryContent(data=b"\x89PNG" * 100_000, media_type="image/png")
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}):
        out = cap_mcp_result([image, "z" * 5000, "short"])
    assert out[0] is image
    assert "[TRUNCATED]" in out[1] and len(out[1]) < 600
    assert out[2] == "short"


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
    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
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

    with (
        patch("os.path.expanduser", return_value=home_dir),
        patch("os.getcwd", return_value=sub_dir),
    ):

        toolsets = load_mcp_config()

        assert len(toolsets) == 1
        assert isinstance(toolsets[0], MCPToolset)
        transport = toolsets[0].client.transport
        assert isinstance(transport, StdioTransport)
        assert transport.command == "cmd2"

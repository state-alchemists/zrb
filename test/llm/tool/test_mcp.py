import json
import os
import tempfile
from unittest.mock import patch

import pytest
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from zrb.config.config import CFG
from zrb.llm.tool.mcp import cap_mcp_result, frame_mcp_result, load_mcp_config
from zrb.llm.tool_call.untrusted_data import UNTRUSTED_DATA_NOTE


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


def test_frame_mcp_result_notes_a_string_result():
    out = frame_mcp_result("some server output")
    assert out == f"some server output\n\n[{UNTRUSTED_DATA_NOTE}]"


def test_frame_mcp_result_adds_content_is_to_a_dict():
    out = frame_mcp_result({"data": [1, 2, 3]})
    assert out == {"data": [1, 2, 3], "content_is": UNTRUSTED_DATA_NOTE}


def test_frame_mcp_result_does_not_override_an_existing_content_is():
    out = frame_mcp_result({"content_is": "already labeled"})
    assert out == {"content_is": "already labeled"}


def test_frame_mcp_result_frames_each_string_item_in_a_list():
    out = frame_mcp_result(["a", "b"])
    assert out == [f"a\n\n[{UNTRUSTED_DATA_NOTE}]", f"b\n\n[{UNTRUSTED_DATA_NOTE}]"]


def test_frame_mcp_result_passes_binary_through_untouched():
    """Same rationale as test_cap_mcp_result_passes_binary_through_intact —
    stringifying rich content would destroy it, not just re-frame it."""
    from pydantic_ai.messages import BinaryContent

    image = BinaryContent(data=b"\x89PNG" * 100_000, media_type="image/png")
    assert frame_mcp_result(image) is image


def test_cap_mcp_result_caps_text_items_but_keeps_binary_in_list():
    from pydantic_ai.messages import BinaryContent

    image = BinaryContent(data=b"\x89PNG" * 100_000, media_type="image/png")
    # Ordered so the budget is still open when each item is reached: binary is
    # not charged, "short" costs 5 chars, the long string absorbs the rest.
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}):
        out = cap_mcp_result([image, "short", "z" * 5000])
    assert out[0] is image
    assert out[1] == "short"
    assert "[TRUNCATED]" in out[2] and len(out[2]) < 600


def test_cap_mcp_result_keeps_binary_after_the_budget_is_exhausted():
    """Position must not decide whether an image survives.

    Regression: once the shared budget hit zero the loop replaced every remaining
    part with an omission marker, so an image behind a large text part was
    dropped — the exact loss the binary pass-through exists to prevent. Binary
    costs no text budget, so it is never dropped for lack of one.
    """
    from pydantic_ai.messages import BinaryContent

    image = BinaryContent(data=b"\x89PNG" * 100_000, media_type="image/png")
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}):
        out = cap_mcp_result(["z" * 5000, image, "dropped text"])
    assert image in out, "image dropped by budget exhaustion"
    assert "[TRUNCATED]" in out[0]
    assert "dropped text" not in out
    assert "more parts" in out[-1]


def test_cap_mcp_result_bounds_a_list_in_aggregate():
    """Regression: per-item capping bounded nothing.

    Each of N parts sitting just under the cap passed through untouched, so the
    total was N x the budget — the same per-request overflow the cap exists to
    prevent. The budget is shared across the whole structure now.
    """
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}):
        out = cap_mcp_result(["y" * 400] * 50)
    total = sum(len(item) for item in out)
    # 50 x 400 = 20_000 chars of input; the whole result stays near the budget.
    assert total < 700, total
    assert "more parts" in out[-1]


def test_cap_mcp_result_bounds_nested_lists_in_aggregate():
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}):
        out = cap_mcp_result([["y" * 400] * 10, ["z" * 400] * 10])

    def total_len(value):
        if isinstance(value, str):
            return len(value)
        return sum(total_len(item) for item in value)

    assert total_len(out) < 700, total_len(out)


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

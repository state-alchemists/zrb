import json
import os
import tempfile
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.usage import RunUsage
from pydantic_core import SchemaValidator, core_schema

from zrb.config.config import CFG
from zrb.llm.tool.mcp import (
    add_purpose_to_mcp_tools,
    cap_mcp_result,
    frame_mcp_result,
    load_mcp_config,
)
from zrb.llm.tool.purpose import (
    DECLARED_PURPOSE_KEY,
    PURPOSE_DESCRIPTION,
    with_declared_purpose,
)
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
    """A large image must never be stringified into a truncated repr."""
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
    """An image survives even after the text budget is exhausted."""
    from pydantic_ai.messages import BinaryContent

    image = BinaryContent(data=b"\x89PNG" * 100_000, media_type="image/png")
    with patch.dict(os.environ, {f"{CFG.ENV_PREFIX}_LLM_MAX_OUTPUT_CHARS": "500"}):
        out = cap_mcp_result(["z" * 5000, image, "dropped text"])
    assert image in out, "image dropped by budget exhaustion"
    assert "[TRUNCATED]" in out[0]
    assert "dropped text" not in out
    assert "more parts" in out[-1]


def test_cap_mcp_result_bounds_a_list_in_aggregate():
    """The budget is shared across a list, not applied per item."""
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
        patch("zrb.llm.agent.types.MCPToolset", side_effect=_fake_mcp_toolset),
        patch("zrb.llm.tool.mcp.zrb_print") as mock_print,
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
        patch("zrb.llm.tool.mcp.zrb_print") as mock_print,
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


def _purpose_schema(**extra: object) -> dict:
    """An MCP tool's input schema: one required text argument, closed object."""
    return {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
        **extra,
    }


def test_with_declared_purpose_adds_a_required_argument():
    schema = with_declared_purpose(_purpose_schema())
    assert schema is not None
    assert schema["properties"]["purpose"]["type"] == "string"
    assert schema["properties"]["purpose"]["description"] == PURPOSE_DESCRIPTION
    # Required, not optional: an optional property turns a provider's strict
    # mode off for the whole tool.
    assert schema["required"] == ["text", "purpose"]
    assert schema["additionalProperties"] is False


def test_with_declared_purpose_leaves_a_servers_own_purpose_alone():
    """A server that declares `purpose` means it — forwarding it is the point."""
    own = _purpose_schema(
        properties={"text": {"type": "string"}, "purpose": {"type": "string"}}
    )
    assert with_declared_purpose(own) is None


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "#/$defs/args"},
        {"type": "array", "items": {"type": "string"}},
        {"type": "object", "properties": "not-a-mapping"},
        {},
    ],
)
def test_with_declared_purpose_leaves_an_unsafe_schema_alone(schema):
    assert with_declared_purpose(schema) is None


class _RecordingToolset(AbstractToolset[None]):
    """A stand-in for an MCP server: one tool, and what it was called with."""

    def __init__(self, tool_def: ToolDefinition) -> None:
        self.tool_def = tool_def
        self.calls: "list[tuple[str, dict]]" = []

    @property
    def id(self) -> str | None:
        return "recording"

    async def get_tools(self, ctx):
        return {
            self.tool_def.name: ToolsetTool(
                toolset=self,
                tool_def=self.tool_def,
                max_retries=1,
                args_validator=SchemaValidator(core_schema.any_schema()),
            )
        }

    async def call_tool(self, name, tool_args, ctx, tool):
        self.calls.append((name, tool_args))
        return "ok"


def _run_context() -> RunContext[None]:
    return RunContext(deps=None, model=MagicMock(), usage=RunUsage())


def _tool_def(with_own_purpose: bool) -> ToolDefinition:
    schema = _purpose_schema()
    if with_own_purpose:
        schema["properties"]["purpose"] = {"type": "string"}
    return ToolDefinition(name="echo", parameters_json_schema=schema)


@pytest.mark.asyncio
async def test_purpose_is_offered_and_then_dropped_before_the_server():
    """Both halves: the model may write the line, the server never sees it."""
    inner = _RecordingToolset(_tool_def(with_own_purpose=False))
    toolset = add_purpose_to_mcp_tools(inner)
    tools = await toolset.get_tools(_run_context())

    tool_def = tools["echo"].tool_def
    assert "purpose" in tool_def.parameters_json_schema["properties"]
    assert tool_def.metadata[DECLARED_PURPOSE_KEY] is True

    await toolset.call_tool(
        "echo",
        {"text": "hi", "purpose": "Echoing the probe"},
        _run_context(),
        tools["echo"],
    )
    assert inner.calls == [("echo", {"text": "hi"})]


@pytest.mark.asyncio
async def test_a_servers_own_purpose_is_forwarded():
    inner = _RecordingToolset(_tool_def(with_own_purpose=True))
    toolset = add_purpose_to_mcp_tools(inner)
    tools = await toolset.get_tools(_run_context())

    tool_def = tools["echo"].tool_def
    assert tool_def.parameters_json_schema["properties"]["purpose"] == {
        "type": "string"
    }
    assert DECLARED_PURPOSE_KEY not in (tool_def.metadata or {})

    await toolset.call_tool(
        "echo",
        {"text": "hi", "purpose": "the server's own"},
        _run_context(),
        tools["echo"],
    )
    assert inner.calls == [("echo", {"text": "hi", "purpose": "the server's own"})]


@pytest.mark.asyncio
async def test_an_unsafe_schema_keeps_its_call_arguments_untouched():
    """Nothing was declared, so nothing may be dropped."""
    odd = ToolDefinition(name="echo", parameters_json_schema={"$ref": "#/$defs/a"})
    inner = _RecordingToolset(odd)
    toolset = add_purpose_to_mcp_tools(inner)
    tools = await toolset.get_tools(_run_context())

    await toolset.call_tool(
        "echo", {"text": "hi", "purpose": "kept"}, _run_context(), tools["echo"]
    )
    assert inner.calls == [("echo", {"text": "hi", "purpose": "kept"})]

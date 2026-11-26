"""What an MCP server returns, and the `purpose` line it may receive.

Discovery and trust of `mcp-config.json` — which files load and what may be
started from them — lives in `test_mcp_config.py`.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.tools import RunContext, ToolDefinition
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.usage import RunUsage
from pydantic_core import SchemaValidator, core_schema

from zrb.config.config import CFG
from zrb.llm.capabilities.tool.mcp import (
    add_purpose_to_mcp_tools,
    cap_mcp_result,
    frame_mcp_result,
)
from zrb.llm.capabilities.tool.purpose import (
    DECLARED_PURPOSE_KEY,
    PURPOSE_DESCRIPTION,
    with_declared_purpose,
)
from zrb.llm.capabilities.tool_call.untrusted_data import UNTRUSTED_DATA_NOTE


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

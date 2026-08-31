"""Tests for the lossless tool-result spill store (ADR-0089)."""

from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.agent.spill import (
    LocalFileStore,
    build_spill_preview,
    json_sketch,
    maybe_spill,
    read_tool_result,
    to_bytes,
)

# --- LocalFileStore ---------------------------------------------------------


def test_store_write_read_roundtrip(tmp_path):
    store = LocalFileStore(base_dir=tmp_path)
    handle = store.write("run/call.0", b"alpha\nbeta\ngamma")
    assert handle == "run/call.0"
    assert store.read(handle) == b"alpha\nbeta\ngamma"


def test_store_rejects_a_symlinked_root(tmp_path):
    real_root = tmp_path / "real-root"
    real_root.mkdir()
    spill_root = tmp_path / "spill-root"
    spill_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(PermissionError):
        LocalFileStore(base_dir=spill_root).write("secret", b"not written")

    assert not list(real_root.iterdir())


def test_store_read_neutralizes_path_traversal(tmp_path):
    store = LocalFileStore(base_dir=tmp_path)
    store.write("safe", b"x")
    # Sanitization turns ".." into "_" and drops leading separators, so a
    # traversal handle names a different (nonexistent) key rather than escaping.
    with pytest.raises(OSError):
        store.read("../safe")
    with pytest.raises(OSError):
        store.read("/etc/passwd")


def test_store_read_rejects_symlink_escape(tmp_path):
    store = LocalFileStore(base_dir=tmp_path)
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret")
    (tmp_path / "link").symlink_to(outside)
    with pytest.raises(PermissionError):
        store.read("link")


def test_store_missing_handle_raises_oserror(tmp_path):
    store = LocalFileStore(base_dir=tmp_path)
    with pytest.raises(OSError):
        store.read("nope")


# --- serialization helpers --------------------------------------------------


def test_to_bytes():
    assert to_bytes("hi") == b"hi"
    assert to_bytes(b"\x00\x01") == b"\x00\x01"
    assert to_bytes({"a": 1}) == b'{"a": 1}'


def test_json_sketch():
    assert json_sketch({"a": 1, "b": "x"}) == "{'a': int, 'b': str}"
    assert json_sketch([1, 2, 3]) == "[3 items of int]"
    assert json_sketch("plain") == ""


def test_build_spill_preview_text_and_binary():
    # preview_chars < len → head/tail with the middle elided.
    preview = build_spill_preview("h1", "abcdef", preview_chars=4)
    assert "h1" in preview
    assert "ab" in preview and "ef" in preview
    assert "cd" not in preview
    assert "ReadToolResult" in preview
    binary = build_spill_preview("h2", b"\x00" * 100, preview_chars=10)
    assert "binary" in binary


def test_read_tool_result_has_a_pascal_case_tool_name():
    assert read_tool_result.__name__ == "ReadToolResult"


# --- maybe_spill ------------------------------------------------------------


@pytest.fixture
def spill_store(tmp_path, monkeypatch):
    store = LocalFileStore(base_dir=tmp_path)
    monkeypatch.setattr("zrb.llm.agent.spill.default_spill_store", store)
    return store


def _enable_spill(monkeypatch, on=True):
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_ENABLE_TOOL_SPILL", on)


def test_maybe_spill_disabled_returns_unchanged(monkeypatch, spill_store):
    _enable_spill(monkeypatch, on=False)
    value = "x" * 500
    out, meta = maybe_spill(value, limit=10)
    assert out == value
    assert meta == {}


def test_maybe_spill_under_limit_unchanged(monkeypatch, spill_store):
    _enable_spill(monkeypatch, on=True)
    value = "short"
    out, meta = maybe_spill(value, limit=100)
    assert out == value
    assert meta == {}


def test_maybe_spill_oversized(monkeypatch, spill_store):
    _enable_spill(monkeypatch, on=True)
    value = "z" * 500
    out, meta = maybe_spill(value, limit=100)
    assert out != value
    assert "stored to handle" in out
    assert "ReadToolResult" in out
    handle = meta["overflow_handle"]
    assert spill_store.read(handle) == b"z" * 500
    assert meta["overflow_chars"] == 500


def test_maybe_spill_multimodal_unchanged(monkeypatch, spill_store):
    _enable_spill(monkeypatch, on=True)
    monkeypatch.setattr("zrb.llm.agent.spill.has_multimodal", lambda v: True)
    value = {"big": "x" * 500}
    out, meta = maybe_spill(value, limit=10)
    assert out == value
    assert meta == {}


def test_maybe_spill_respects_sandbox_deny_read(monkeypatch, spill_store, tmp_path):
    from zrb.llm.sandbox import SandboxPolicy, sandbox_policy

    _enable_spill(monkeypatch)
    with sandbox_policy(SandboxPolicy(enabled=True, deny_read_paths=(str(tmp_path),))):
        out, meta = maybe_spill("z" * 500, limit=100)

    assert out == "z" * 500
    assert meta == {}


# --- read_tool_result -------------------------------------------------------


def test_read_tool_result_slices_and_filters(monkeypatch, spill_store):
    _enable_spill(monkeypatch, on=True)
    handle = spill_store.write("k", b"apple\nbanana\ncherry\ndate")
    out = read_tool_result(handle, offset=1, limit=2)
    assert "banana" in out and "cherry" in out
    assert "apple" not in out and "date" not in out
    out = read_tool_result(handle, from_end=True, limit=1)
    assert "date" in out
    out = read_tool_result(handle, pattern="an")
    assert "banana" in out and "cherry" not in out


def test_read_tool_result_bad_args_and_handle(monkeypatch, spill_store):
    _enable_spill(monkeypatch, on=True)
    out = read_tool_result("missing-handle")
    assert "No stored tool result" in out
    out = read_tool_result("missing-handle", offset=-1)
    assert "offset" in out


def test_read_tool_result_respects_sandbox_deny_read(
    monkeypatch, spill_store, tmp_path
):
    from zrb.llm.sandbox import SandboxPolicy, sandbox_policy

    _enable_spill(monkeypatch)
    handle = spill_store.write("blocked", b"secret")
    with sandbox_policy(SandboxPolicy(enabled=True, deny_read_paths=(str(tmp_path),))):
        out = read_tool_result(handle)

    assert "Blocked by sandbox policy" in out


# --- wrapper integration ----------------------------------------------------


@pytest.mark.asyncio
async def test_wrapper_defers_spill_until_after_post_tool_use(monkeypatch, spill_store):
    from pydantic_ai import ToolReturn

    from zrb.llm.agent.common import create_safe_wrapper

    _enable_spill(monkeypatch, on=True)
    big = "z" * 5000

    def tool():
        return big

    wrapped = create_safe_wrapper(tool)
    result = await wrapped()

    assert isinstance(result, ToolReturn)
    assert result.return_value == big
    assert not result.metadata


@pytest.mark.asyncio
async def test_toolset_spills_oversized_when_enabled(monkeypatch, spill_store):
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset

    _enable_spill(monkeypatch)
    wrapped_toolset = wrap_toolset(FunctionToolset(tools=[]))
    big = "z" * 5000
    with (
        patch("zrb.llm.agent.common.CFG") as mock_cfg,
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool",
            new_callable=AsyncMock,
            return_value=big,
        ),
    ):
        mock_cfg.LLM_MAX_TOOL_RESULT_CHARS = 1000
        result = await cast(Any, wrapped_toolset).call_tool(
            "external_tool", {}, None, None
        )

    assert isinstance(result, ToolReturn)
    assert isinstance(result.return_value, str)
    assert "stored to handle" in result.return_value
    handle = result.metadata["overflow_handle"]
    assert spill_store.read(handle) == big.encode()


@pytest.mark.asyncio
async def test_read_tool_result_does_not_spill_its_page(monkeypatch, spill_store):
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import FunctionToolset

    from zrb.llm.agent.common import wrap_toolset

    _enable_spill(monkeypatch)
    wrapped_toolset = wrap_toolset(FunctionToolset(tools=[]))
    page = "alpha\nbeta"
    with (
        patch("zrb.llm.agent.common.CFG") as mock_cfg,
        patch(
            "pydantic_ai.toolsets.WrapperToolset.call_tool",
            new_callable=AsyncMock,
            return_value=page,
        ),
    ):
        mock_cfg.LLM_MAX_TOOL_RESULT_CHARS = 1
        result = await cast(Any, wrapped_toolset).call_tool(
            "ReadToolResult", {}, None, None
        )

    assert isinstance(result, ToolReturn)
    assert result.return_value == page
    assert not result.metadata

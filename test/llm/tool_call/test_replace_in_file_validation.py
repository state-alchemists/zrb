import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolDenied

from zrb.llm.tool_call.tool_policy.replace_in_file_validation import (
    replace_in_file_validation_policy,
)


@pytest.mark.asyncio
async def test_replace_in_file_validation_mismatch_name():
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "OtherTool"
    next_handler = AsyncMock(return_value="next_result")

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert result == "next_result"
    next_handler.assert_called_once()


@pytest.mark.asyncio
async def test_replace_in_file_validation_identical_text():
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "Edit"
    call.args = {"path": "test.txt", "old_text": "hello", "new_text": "hello"}
    next_handler = AsyncMock()

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert isinstance(result, ToolDenied)
    assert "identical" in result.message


@pytest.mark.asyncio
async def test_replace_in_file_validation_file_not_found():
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "Edit"
    call.args = {
        "path": "non_existent_file.txt",
        "old_text": "hello",
        "new_text": "world",
    }
    next_handler = AsyncMock()

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert isinstance(result, ToolDenied)
    assert "File not found" in result.message


@pytest.mark.asyncio
async def test_replace_in_file_validation_text_not_found(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("content here")

    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "Edit"
    call.args = {"path": str(test_file), "old_text": "missing", "new_text": "world"}
    next_handler = AsyncMock()

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert isinstance(result, ToolDenied)
    assert "Old text not found" in result.message
    assert "Please read the file first" in result.message


@pytest.mark.asyncio
async def test_replace_in_file_validation_success(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "Edit"
    call.args = {"path": str(test_file), "old_text": "hello", "new_text": "hi"}
    next_handler = AsyncMock(return_value="success")

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert result == "success"
    next_handler.assert_called_once()


@pytest.mark.asyncio
async def test_replace_in_file_validation_json_string_args(tmp_path):
    """JSON string args are parsed and validated."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "Edit"
    import json
    call.args = json.dumps({
        "path": str(test_file), "old_text": "hello", "new_text": "hi"
    })
    next_handler = AsyncMock(return_value="success")

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert result == "success"
    next_handler.assert_called_once()


@pytest.mark.asyncio
async def test_replace_in_file_validation_invalid_json_passes_through():
    """Invalid JSON string delegates to next handler."""
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "Edit"
    call.args = "not valid json"
    next_handler = AsyncMock(return_value="next_result")

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert result == "next_result"
    next_handler.assert_called_once()


@pytest.mark.asyncio
async def test_replace_in_file_validation_non_dict_args_passes_through():
    """Non-dict args delegate to next handler."""
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "Edit"
    call.args = ["not", "a", "dict"]
    next_handler = AsyncMock(return_value="next_result")

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert result == "next_result"
    next_handler.assert_called_once()


@pytest.mark.asyncio
async def test_replace_in_file_validation_missing_args_passes_through():
    """Missing required args (path/old_text/new_text) delegates to next handler."""
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "Edit"
    call.args = {"path": "some_file.txt"}  # missing old_text and new_text
    next_handler = AsyncMock(return_value="next_result")

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert result == "next_result"
    next_handler.assert_called_once()


@pytest.mark.asyncio
async def test_replace_in_file_validation_read_error(tmp_path, monkeypatch):
    """File read error returns ToolDenied."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "Edit"
    call.args = {"path": str(test_file), "old_text": "hello", "new_text": "hi"}
    next_handler = AsyncMock()

    import builtins
    original_open = builtins.open

    def mock_open(path, *args, **kwargs):
        if str(test_file) in str(path):
            raise PermissionError("permission denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", mock_open)

    result = await replace_in_file_validation_policy(ui, call, next_handler)

    assert isinstance(result, ToolDenied)
    assert "Error reading file" in result.message

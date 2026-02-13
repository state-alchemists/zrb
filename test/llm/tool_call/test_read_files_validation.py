import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolDenied

from zrb.llm.tool_call.tool_policy.read_files_validation import (
    read_files_validation_policy,
)


@pytest.mark.asyncio
async def test_read_files_validation_mismatch_name():
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "OtherTool"
    next_handler = AsyncMock(return_value="next_result")

    result = await read_files_validation_policy(ui, call, next_handler)

    assert result == "next_result"
    next_handler.assert_called_once()


@pytest.mark.asyncio
async def test_read_files_validation_read_many_none_found():
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "ReadMany"
    call.args = {"paths": ["missing1.txt", "missing2.txt"]}
    next_handler = AsyncMock()

    result = await read_files_validation_policy(ui, call, next_handler)

    assert isinstance(result, ToolDenied)
    assert "None of the files were found" in result.message


@pytest.mark.asyncio
async def test_read_files_validation_read_many_partial_success(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")

    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "ReadMany"
    call.args = {"paths": [str(test_file), "missing.txt"]}
    next_handler = AsyncMock(return_value="success")

    result = await read_files_validation_policy(ui, call, next_handler)

    assert result == "success"
    next_handler.assert_called_once()

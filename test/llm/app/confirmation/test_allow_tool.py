from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolApproved

from zrb.llm.app.confirmation.allow_tool import allow_tool_usage


@pytest.mark.asyncio
async def test_allow_tool_usage_match_no_kwargs():
    # Setup
    middleware = allow_tool_usage("my_tool")
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "my_tool"
    call.args = {"a": 1}
    next_handler = AsyncMock()

    # Execute
    result = await middleware(ui, call, "", next_handler)

    # Assert
    assert isinstance(result, ToolApproved)
    next_handler.assert_not_called()


@pytest.mark.asyncio
async def test_allow_tool_usage_mismatch_name():
    # Setup
    middleware = allow_tool_usage("my_tool")
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "other_tool"
    call.args = {}
    next_handler = AsyncMock(return_value="next_result")

    # Execute
    result = await middleware(ui, call, "", next_handler)

    # Assert
    assert result == "next_result"
    next_handler.assert_called_once()


@pytest.mark.asyncio
async def test_allow_tool_usage_match_kwargs_success():
    # Setup
    middleware = allow_tool_usage("my_tool", {"param": "^valid_"})
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "my_tool"
    call.args = {"param": "valid_value", "other": "ignored"}
    next_handler = AsyncMock()

    # Execute
    result = await middleware(ui, call, "", next_handler)

    # Assert
    assert isinstance(result, ToolApproved)
    next_handler.assert_not_called()


@pytest.mark.asyncio
async def test_allow_tool_usage_match_kwargs_fail():
    # Setup
    middleware = allow_tool_usage("my_tool", {"param": "^valid_"})
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "my_tool"
    call.args = {"param": "invalid_value"}
    next_handler = AsyncMock(return_value="next_result")

    # Execute
    result = await middleware(ui, call, "", next_handler)

    # Assert
    assert result == "next_result"
    next_handler.assert_called_once()


@pytest.mark.asyncio
async def test_allow_tool_usage_match_kwargs_param_missing_in_args():
    # Setup
    # "param" is in kwargs but NOT in args.
    # Logic: "all parameter in the call parameter has to match..."
    # Since "param" is NOT in call parameter, it doesn't have to match.
    middleware = allow_tool_usage("my_tool", {"param": "^valid_"})
    ui = MagicMock()
    call = MagicMock()
    call.tool_name = "my_tool"
    call.args = {"other": "stuff"}
    next_handler = AsyncMock()

    # Execute
    result = await middleware(ui, call, "", next_handler)

    # Assert
    assert isinstance(result, ToolApproved)
    next_handler.assert_not_called()

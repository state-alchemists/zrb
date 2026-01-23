from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolApproved, ToolDenied

from zrb.llm.tool_call import ToolCallHandler


@pytest.mark.asyncio
async def test_pre_confirmation_approved():
    ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="y")
    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {}

    async def pre_middleware(ui, call, next_middleware):
        return ToolApproved()

    handler = ToolCallHandler(tool_policies=[pre_middleware])
    result = await handler.handle(ui, call)

    assert isinstance(result, ToolApproved)
    ui.ask_user.assert_not_called()


@pytest.mark.asyncio
async def test_pre_confirmation_denied():
    ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="y")
    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {}

    async def pre_middleware(ui, call, next_middleware):
        return ToolDenied("Denied")

    handler = ToolCallHandler(tool_policies=[pre_middleware])
    result = await handler.handle(ui, call)

    assert isinstance(result, ToolDenied)
    ui.ask_user.assert_not_called()


@pytest.mark.asyncio
async def test_pre_confirmation_next():
    ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="y")  # Allow in post check
    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {}

    async def pre_middleware(ui, call, next_middleware):
        return await next_middleware(ui, call)

    async def post_middleware(u, c, r, n):
        return ToolApproved() if r == "y" else ToolDenied("No")

    handler = ToolCallHandler(
        tool_policies=[pre_middleware],
        response_handlers=[post_middleware],
    )
    result = await handler.handle(ui, call)

    assert isinstance(result, ToolApproved)
    ui.ask_user.assert_called_once()


@pytest.mark.asyncio
async def test_confirmation_message_middleware():
    ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="y")
    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {"key": "value"}

    async def msg_middleware(ui, call, args_section):
        return "Modified Args"

    async def post_middleware(u, c, r, n):
        return ToolApproved()

    handler = ToolCallHandler(
        argument_formatters=[msg_middleware],
        response_handlers=[post_middleware],
    )
    await handler.handle(ui, call)

    # Check that append_to_output was called with "Modified Args"
    args, _ = ui.append_to_output.call_args
    assert "Modified Args" in args[0]


@pytest.mark.asyncio
async def test_post_confirmation_middleware():
    ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="n")
    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {}

    async def post_middleware(ui, call, response, next_middleware):
        if response == "n":
            return ToolDenied("User said no")
        return await next_middleware(ui, call, response)

    handler = ToolCallHandler(response_handlers=[post_middleware])
    result = await handler.handle(ui, call)

    assert isinstance(result, ToolDenied)

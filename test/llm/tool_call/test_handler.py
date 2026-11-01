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


from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolApproved, ToolDenied

from zrb.llm.tool_call import ToolCallHandler


@pytest.mark.asyncio
async def test_handler_explicit_approval():
    ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="y")
    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {}

    handler = ToolCallHandler()
    result = await handler.handle(ui, call)

    assert isinstance(result, ToolApproved)


@pytest.mark.asyncio
async def test_handler_explicit_denial():
    ui = MagicMock()
    ui.ask_user = AsyncMock(return_value="n")
    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {}

    handler = ToolCallHandler()
    result = await handler.handle(ui, call)

    assert isinstance(result, ToolDenied)
    assert result.message == "User denied"


@pytest.mark.asyncio
async def test_handler_empty_answer_approves():
    ui = MagicMock()
    # A bare Enter approves, and the handler returns immediately.
    ui.ask_user = AsyncMock(side_effect=[""])
    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {}

    handler = ToolCallHandler()
    result = await handler.handle(ui, call)

    assert isinstance(result, ToolApproved)
    assert ui.ask_user.await_count == 1


@pytest.mark.asyncio
async def test_handler_feedback_denial():
    ui = MagicMock()
    # Simulate user typing a reason
    ui.ask_user = AsyncMock(return_value="I don't think this is safe")
    call = MagicMock()
    call.tool_name = "test_tool"
    call.args = {}

    handler = ToolCallHandler()
    result = await handler.handle(ui, call)

    assert isinstance(result, ToolDenied)
    assert (
        "User denied execution with message: I don't think this is safe"
        in result.message
    )


@pytest.mark.asyncio
async def test_response_handlers_run_in_order_and_the_fallback_answers_last():
    from zrb.llm.tool_call.handler import run_response_handlers

    seen = []

    async def first(ui, call, response, next_handler):
        seen.append("first")
        return await next_handler(ui, call, response + "+first")

    async def second(ui, call, response, next_handler):
        seen.append("second")
        return await next_handler(ui, call, response + "+second")

    async def fallback(ui, call, response):
        seen.append("fallback")
        return response

    result = await run_response_handlers([first, second], None, None, "r", fallback)

    assert result == "r+first+second"
    assert seen == ["first", "second", "fallback"]


@pytest.mark.asyncio
async def test_a_response_handler_that_answers_skips_the_rest_and_the_fallback():
    from zrb.llm.tool_call.handler import run_response_handlers

    async def answers(ui, call, response, next_handler):
        return ToolDenied("stop")

    async def never(ui, call, response, next_handler):
        raise AssertionError("not reached")

    async def fallback(ui, call, response):
        raise AssertionError("not reached")

    result = await run_response_handlers([answers, never], None, None, "r", fallback)

    assert isinstance(result, ToolDenied)

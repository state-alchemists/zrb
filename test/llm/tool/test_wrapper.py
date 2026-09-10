import pytest

from zrb.llm.tool.wrapper import tool_safe_async


@pytest.mark.asyncio
async def test_tool_safe_async_callable_hint():
    def hint_factory(name):
        return f"Check {name}"

    @tool_safe_async(error_hint=hint_factory)
    async def failing_tool(name):
        raise ValueError("Oops")

    res = await failing_tool("mytool")
    assert "Error in failing_tool: Oops" in res.return_value
    assert "[SYSTEM SUGGESTION]: Check mytool" in res.return_value


@pytest.mark.asyncio
async def test_tool_safe_async_callable_hint_exception():
    def hint_factory(name):
        raise RuntimeError("Hint fail")

    @tool_safe_async(error_hint=hint_factory)
    async def failing_tool(name):
        raise ValueError("Oops")

    res = await failing_tool("mytool")
    assert "Error in failing_tool: Oops" in res.return_value
    # Should not include hint if factory failed
    assert "[SYSTEM SUGGESTION]" not in res.return_value


@pytest.mark.asyncio
async def test_tool_safe_async_empty_error_message():
    @tool_safe_async
    async def failing_tool():
        raise ValueError("")

    res = await failing_tool()
    assert "Error in failing_tool: ValueError" in res.return_value


@pytest.mark.asyncio
async def test_tool_safe_async_no_args():
    @tool_safe_async()  # test with parens but no args
    async def failing_tool():
        raise ValueError("Fail")

    res = await failing_tool()
    assert "Error" in res.return_value


@pytest.mark.asyncio
async def test_tool_safe_async_tags_error_metadata():
    """The caught exception's ToolReturn carries error=True, matching the
    same metadata convention create_safe_wrapper uses for every other tool's
    exception path (agent/common.py) — so a structured consumer can tell this
    apart from a normal success without string-sniffing.
    """

    @tool_safe_async
    async def failing_tool():
        raise ValueError("Oops")

    res = await failing_tool()
    assert res.metadata.get("error") is True

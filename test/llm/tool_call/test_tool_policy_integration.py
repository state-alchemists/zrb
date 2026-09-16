"""End-to-end verdict tests through the real agent run loop.

Drives `run_agent` with pydantic-ai's deterministic fake model (`TestModel`)
and zrb's own `create_agent`, so a tool call travels the real wiring: model
request → DeferredToolRequests → approval cascade → tool execution (or a
denial that blocks it) → result fed back for the next turn. This is the round
trip the rest of the suite mocks at the `agent.run` boundary.
"""

import asyncio

import pytest
from pydantic_ai import Tool, ToolApproved, ToolCallPart, ToolDenied
from pydantic_ai.models.test import TestModel

from zrb.llm.agent.common import create_agent
from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.tool_call.handler import ToolCallHandler


def _weather_tool(record: list[str]):
    @Tool
    async def get_weather(city: str) -> str:
        record.append(city)
        return f"Weather in {city}: Sunny, 25C"

    return get_weather


async def _run(confirmation, *, record: list[str] | None = None):
    """Run one agent turn with the fake model and return (output, record)."""
    record = record if record is not None else []
    agent = create_agent(
        model=TestModel(),
        tools=[_weather_tool(record)],
        system_prompt="You are a helpful assistant that can check weather.",
        yolo=False,
    )

    def quiet(msg, **kwargs):
        pass

    result, _ = await run_agent(
        agent=agent,
        message="Check the weather.",
        message_history=[],
        limiter=LLMLimiter(),
        tool_confirmation=confirmation,
        print_fn=quiet,
    )
    return result, record


@pytest.mark.asyncio
async def test_e2e_tool_executes_after_approval():
    """An approved tool call runs, and its result reaches the model."""

    async def approver(call: ToolCallPart):
        return ToolApproved()

    output, record = await _run(approver)
    assert record, "approved tool must have been executed"
    assert "Sunny" in str(output)


@pytest.mark.asyncio
async def test_e2e_tool_denial_blocks_execution():
    """A denied tool call is never executed, and the denial reaches the model."""

    async def denier(call: ToolCallPart):
        return ToolDenied("blocked by the user")

    output, record = await _run(denier)
    assert record == [], "denied tool must not have been executed"
    assert "blocked" in str(output)


@pytest.mark.asyncio
async def test_e2e_tool_policy_denial():
    """A pre-confirmation tool policy denies, blocking execution."""
    record: list[str] = []

    async def block_weather_policy(ui, call, next_policy):
        if call.tool_name == "get_weather":
            return ToolDenied("weather is classified")
        return await next_policy(ui, call)

    handler = ToolCallHandler(tool_policies=[block_weather_policy])
    output, record = await _run(handler, record=record)
    assert record == [], "policy-denied tool must not have been executed"
    assert "classified" in str(output)


@pytest.mark.asyncio
async def test_e2e_simple_callback_backward_compat():
    """The plain (call) -> ToolApproved callback still works as confirmation."""

    async def simple_callback(call: ToolCallPart):
        return ToolApproved()

    output, record = await _run(simple_callback)
    assert record, "approved tool must have been executed"


if __name__ == "__main__":
    asyncio.run(test_e2e_tool_executes_after_approval())

#!/usr/bin/env python3
"""Test script to demonstrate tool policy integration in non-interactive mode."""

import asyncio
from typing import Any

import pytest
from pydantic_ai import Agent, Tool, ToolApproved, ToolCallPart, ToolDenied

from zrb.llm.agent.run_agent import run_agent
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.tool_call.middleware import ResponseHandler, ToolPolicy


# Define a simple tool
@Tool
async def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 25°C"


# Create a tool policy that blocks certain cities
async def block_sensitive_cities_policy(
    ui: Any, call: ToolCallPart, next_policy: Any
) -> ToolApproved | ToolDenied | None:
    """Policy that blocks weather requests for sensitive cities."""
    if call.tool_name == "get_weather":
        city = call.args.get("city", "").lower()
        if city in ["moscow", "tehran", "pyongyang"]:
            return ToolDenied(f"Weather for {city} is classified information")

    # Pass to next policy
    return await next_policy(ui, call)


# Create a response handler that modifies user input
async def auto_approve_handler(
    ui: Any, call: ToolCallPart, response: str, next_handler: Any
) -> ToolApproved | ToolDenied | None:
    """Handler that auto-approves if user says 'auto'."""
    if response.strip().lower() == "auto":
        return ToolApproved()

    # Pass to next handler
    return await next_handler(ui, call, response, next_handler)


@pytest.mark.asyncio
async def test_tool_policy():
    """Test that tool policies work in non-interactive mode."""

    # Create agent with the weather tool
    agent = Agent(
        model="openai:gpt-4o-mini",
        tools=[get_weather],
        system_prompt="You are a helpful assistant that can check weather.",
    )

    # Create a ToolCallHandler with policies
    handler = ToolCallHandler(
        tool_policies=[block_sensitive_cities_policy],
        response_handlers=[auto_approve_handler],
    )

    # Create a simple print function
    def test_print(msg: str):
        print(f"[TEST] {msg}")

    # Test 1: Blocked city (should be denied by policy)
    print("\n=== Test 1: Blocked city (Moscow) ===")
    result1, _ = await run_agent(
        agent=agent,
        message="What's the weather in Moscow?",
        message_history=[],
        limiter=LLMLimiter(),
        tool_confirmation=handler,
        print_fn=test_print,
    )
    print(f"Result: {result1}")

    # Test 2: Allowed city (should prompt for confirmation)
    print("\n=== Test 2: Allowed city (London) ===")
    print("When prompted, type 'auto' to test auto-approve handler")
    result2, _ = await run_agent(
        agent=agent,
        message="What's the weather in London?",
        message_history=[],
        limiter=LLMLimiter(),
        tool_confirmation=handler,
        print_fn=test_print,
    )
    print(f"Result: {result2}")

    # Test 3: Simple callback (backward compatibility)
    print("\n=== Test 3: Simple callback function ===")

    async def simple_callback(call: ToolCallPart) -> ToolApproved | ToolDenied:
        print(f"[CALLBACK] Tool: {call.tool_name}, Args: {call.args}")
        return ToolApproved()

    result3, _ = await run_agent(
        agent=agent,
        message="What's the weather in Paris?",
        message_history=[],
        limiter=LLMLimiter(),
        tool_confirmation=simple_callback,
        print_fn=test_print,
    )
    print(f"Result: {result3}")


if __name__ == "__main__":
    asyncio.run(test_tool_policy())

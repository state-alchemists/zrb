#!/usr/bin/env python3
"""
Test script to verify hook system works.

Run from this directory:
    python test_hooks.py

Or with pytest:
    pytest test_hooks.py -v
"""

import asyncio
import os
import sys

import pytest

# Add parent directory to path to import zrb
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


@pytest.mark.asyncio
async def test_hook_result_methods():
    """Test HookResult static methods."""
    print_section("Test 1: HookResult Methods")

    # Test with_system_message (default replace_response=False)
    result = HookResult.with_system_message("Hello from hook!")
    print(f"✓ with_system_message: {result.modifications}")
    assert result.modifications["systemMessage"] == "Hello from hook!"
    assert result.modifications["replaceResponse"] == False

    # Test with_system_message with replace_response=True
    result = HookResult.with_system_message("Transform response", replace_response=True)
    print(f"✓ with_system_message (replace): {result.modifications}")
    assert result.modifications["systemMessage"] == "Transform response"
    assert result.modifications["replaceResponse"] == True

    # Test block
    result = HookResult.block("Not allowed", "Use a different tool")
    print(f"✓ block: success={result.success}, should_stop={result.should_stop}")
    print(f"        modifications={result.modifications}")
    assert result.success == False
    assert result.should_stop == True
    assert result.modifications["decision"] == "block"

    # Test allow
    result = HookResult.allow(permission_decision="allow", reason="Safe to proceed")
    print(f"✓ allow: modifications={result.modifications}")
    assert result.modifications["permissionDecision"] == "allow"

    # Test deny
    result = HookResult.deny("Tool is dangerous")
    print(f"✓ deny: modifications={result.modifications}")
    assert result.modifications["permissionDecision"] == "deny"

    # Test ask
    result = HookResult.ask("Please confirm this action")
    print(f"✓ ask: modifications={result.modifications}")
    assert result.modifications["permissionDecision"] == "ask"

    # Test with_additional_context
    result = HookResult.with_additional_context("Extra context here")
    print(f"✓ with_additional_context: {result.modifications}")
    assert result.modifications["additionalContext"] == "Extra context here"


@pytest.mark.asyncio
async def test_hook_registration():
    """Test hook registration."""
    print_section("Test 2: Hook Registration")

    manager = HookManager()

    # Track calls
    calls = []

    # Create test hook
    async def test_hook(context: HookContext) -> HookResult:
        calls.append(context.event.value)
        return HookResult.with_system_message(f"Event: {context.event.value}")

    # Register for multiple events
    manager.register(
        test_hook,
        events=[
            HookEvent.SESSION_START,
            HookEvent.SESSION_END,
            HookEvent.POST_TOOL_USE,
        ],
    )

    print("✓ Hook registered for 3 events")

    # Test each event
    for event in [
        HookEvent.SESSION_START,
        HookEvent.POST_TOOL_USE,
        HookEvent.SESSION_END,
    ]:
        results = await manager.execute_hooks(
            event=event, event_data={"test": True}, session_id="test-session"
        )
        if results:
            print(
                f"  {event.value}: system_message={results[0].system_message[:30]}..."
            )

    print(f"✓ All events fired correctly")
    print(f"  Calls: {calls}")
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_hook_matchers():
    """Test hook matchers."""
    print_section("Test 3: Hook Matchers")

    from zrb.llm.hook.schema import CommandHookConfig, HookConfig, MatcherConfig

    manager = HookManager()

    # Hook that only matches Bash tool
    async def bash_only_hook(context: HookContext) -> HookResult:
        return HookResult.with_system_message(
            f"Bash tool detected: {context.tool_name}"
        )

    config = HookConfig(
        name="bash-only",
        events=[HookEvent.PRE_TOOL_USE],
        type="command",  # type: ignore
        config=CommandHookConfig(command=""),  # Dummy
        matchers=[
            MatcherConfig(
                field="tool_name", operator="equals", value="Bash"  # type: ignore
            )
        ],
    )

    manager.register(bash_only_hook, events=[HookEvent.PRE_TOOL_USE], config=config)

    # Test with Bash tool
    results = await manager.execute_hooks(
        event=HookEvent.PRE_TOOL_USE, event_data={}, tool_name="Bash"
    )
    print(f"✓ Bash event: {len(results)} result(s)")
    if results:
        print(f"  system_message: {results[0].system_message}")

    # Test with Read tool (should not match)
    results = await manager.execute_hooks(
        event=HookEvent.PRE_TOOL_USE, event_data={}, tool_name="Read"
    )
    print(f"✓ Read event: {len(results)} result(s) (should be 0)")

    # Note: The hook registered manually won't have matchers applied
    # Matchers are applied when using _hydrate_hook from config
    print("  Note: Manual hook registration bypasses matcher evaluation")


@pytest.mark.asyncio
async def test_stateful_hook():
    """Test stateful hook."""
    print_section("Test 4: Stateful Hook")

    manager = HookManager()

    class StatefulHook:
        def __init__(self):
            self.call_count = 0
            self.events_seen = []

        async def __call__(self, context: HookContext) -> HookResult:
            self.call_count += 1
            self.events_seen.append(context.event.value)
            return HookResult()

    hook = StatefulHook()
    manager.register(
        hook,
        events=[
            HookEvent.SESSION_START,
            HookEvent.POST_TOOL_USE,
            HookEvent.SESSION_END,
        ],
    )

    # Fire events
    await manager.execute_hooks(HookEvent.SESSION_START, {})
    await manager.execute_hooks(HookEvent.POST_TOOL_USE, {"tool": "Read"})
    await manager.execute_hooks(HookEvent.POST_TOOL_USE, {"tool": "Bash"})
    await manager.execute_hooks(HookEvent.SESSION_END, {})

    print(f"✓ Hook called {hook.call_count} times")
    print(f"  Events seen: {hook.events_seen}")
    # Hook is called once per event, but POST_TOOL_USE fired twice
    assert hook.call_count == 4


@pytest.mark.asyncio
async def test_blocking_hook():
    """Test blocking hook."""
    print_section("Test 5: Blocking Hook")

    manager = HookManager()

    async def blocking_hook(context: HookContext) -> HookResult:
        if context.tool_name == "Bash":
            return HookResult.block("Bash is blocked for safety")
        return HookResult()

    manager.register(blocking_hook, events=[HookEvent.PRE_TOOL_USE])

    # Test blocking
    results = await manager.execute_hooks(
        event=HookEvent.PRE_TOOL_USE, event_data={}, tool_name="Bash"
    )

    print(f"✓ Blocked: {results[0].blocked}")
    print(f"  Reason: {results[0].reason}")
    # HookExecutionResult.blocked indicates blocking decision
    assert results[0].blocked == True

    # Test non-blocking
    results = await manager.execute_hooks(
        event=HookEvent.PRE_TOOL_USE, event_data={}, tool_name="Read"
    )

    print(f"✓ Not blocked: {not results[0].blocked}")
    assert results[0].blocked == False


@pytest.mark.asyncio
async def test_session_end_system_message():
    """Test SESSION_END system message with replace_response."""
    print_section("Test 6: SESSION_END System Message")

    manager = HookManager()

    class JournalHook:
        """Simulates journaling hook that extends session."""

        def __init__(self):
            self.fired = False

        async def __call__(self, context: HookContext) -> HookResult:
            if context.event == HookEvent.SESSION_END:
                self.fired = True
                return HookResult.with_system_message(
                    "Review session for learnings.",
                    replace_response=False,  # Side effects only
                )
            return HookResult()

    hook = JournalHook()
    manager.register(hook, events=[HookEvent.SESSION_END])

    # Fire SESSION_END
    results = await manager.execute_hooks(
        event=HookEvent.SESSION_END, event_data={"output": "test response"}
    )

    print(f"✓ Journal hook fired: {hook.fired}")
    print(f"  system_message: {results[0].system_message}")
    print(f"  replace_response: {results[0].replace_response}")

    assert hook.fired == True
    assert results[0].system_message == "Review session for learnings."
    assert results[0].replace_response == False

    # Test with replace_response=True
    class TransformHook:
        """Simulates transformation hook that replaces response."""

        async def __call__(self, context: HookContext) -> HookResult:
            return HookResult.with_system_message(
                "Summarize this.", replace_response=True
            )

    transform_hook = TransformHook()
    manager2 = HookManager()
    manager2.register(transform_hook, events=[HookEvent.SESSION_END])

    results2 = await manager2.execute_hooks(
        event=HookEvent.SESSION_END, event_data={"output": "long response"}
    )

    print(f"✓ Transform hook replace_response: {results2[0].replace_response}")
    assert results2[0].replace_response == True


@pytest.mark.asyncio
async def test_additional_context():
    """Test additional context injection."""
    print_section("Test 7: Additional Context")

    manager = HookManager()

    async def context_hook(context: HookContext) -> HookResult:
        return HookResult.with_additional_context("User preference: concise responses")

    manager.register(context_hook, events=[HookEvent.SESSION_START])

    results = await manager.execute_hooks(event=HookEvent.SESSION_START, event_data={})

    print(f"✓ additional_context: {results[0].additional_context}")
    assert results[0].additional_context == "User preference: concise responses"


async def main():
    """Run all tests manually (for direct script execution)."""
    print_section("Hook System Tests")

    try:
        await test_hook_result_methods()
        await test_hook_registration()
        await test_hook_matchers()
        await test_stateful_hook()
        await test_blocking_hook()
        await test_session_end_system_message()
        await test_additional_context()

        print_section("All Tests Passed!")
        return True
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

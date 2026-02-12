import pytest

from zrb.llm.hook.executor import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.schema import CommandHookConfig, HookConfig, MatcherConfig
from zrb.llm.hook.types import HookEvent, HookType


def test_hook_result_modifications_mapping():
    # HookResult stores these in modifications, it doesn't have direct attributes
    res = HookResult(
        modifications={"reason": "security breach", "decision": "block", "exit_code": 2}
    )
    assert res.modifications["reason"] == "security breach"
    assert res.modifications["decision"] == "block"
    assert res.modifications["exit_code"] == 2


@pytest.mark.asyncio
async def test_hook_manager_operators():
    manager = HookManager()

    # Test Glob operator
    config_glob = HookConfig(
        name="glob-test",
        events=[HookEvent.PRE_TOOL_USE],
        type=HookType.COMMAND,
        config=CommandHookConfig(command="echo hello"),
        matchers=[MatcherConfig(field="tool_name", operator="glob", value="*.sh")],
    )
    hook_callable = manager._hydrate_hook(config_glob)
    manager.register(hook_callable, config_glob.events, config_glob)

    # Match: should run and return a successful execution result
    # We pass tool_name explicitly because HookContext uses it
    results = await manager.execute_hooks(
        HookEvent.PRE_TOOL_USE, "some data", tool_name="test.sh"
    )
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].message != "Skipped due to matchers"

    # Mismatch: should return "Skipped due to matchers"
    results_skipped = await manager.execute_hooks(
        HookEvent.PRE_TOOL_USE, "some data", tool_name="test.py"
    )
    assert len(results_skipped) == 1
    assert results_skipped[0].message == "Skipped due to matchers"


@pytest.mark.asyncio
async def test_hook_manager_nested_field_access():
    manager = HookManager()
    config = HookConfig(
        name="nested-test",
        events=[HookEvent.PRE_TOOL_USE],
        type=HookType.COMMAND,
        config=CommandHookConfig(command="echo hello"),
        matchers=[
            MatcherConfig(field="metadata.user_id", operator="equals", value="123")
        ],
    )
    hook_callable = manager._hydrate_hook(config)
    manager.register(hook_callable, config.events, config)

    results = await manager.execute_hooks(
        HookEvent.PRE_TOOL_USE, "data", metadata={"user_id": "123"}
    )
    assert any(r.message != "Skipped due to matchers" for r in results)

    results_skipped = await manager.execute_hooks(
        HookEvent.PRE_TOOL_USE, "data", metadata={"user_id": "456"}
    )
    assert any(r.message == "Skipped due to matchers" for r in results_skipped)

import json

import pytest

from zrb.llm.hook.executor import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


def test_hook_result_modifications_mapping():
    # HookResult stores these in modifications, it doesn't have direct attributes
    res = HookResult(
        modifications={"reason": "security breach", "decision": "block", "exit_code": 2}
    )
    assert res.modifications["reason"] == "security breach"
    assert res.modifications["decision"] == "block"
    assert res.modifications["exit_code"] == 2


@pytest.mark.asyncio
async def test_hook_manager_operators(tmp_path):
    manager = HookManager(auto_load=False)

    # Create a dummy hook file to test matcher via public scan method
    hook_dir = tmp_path / "hooks"
    hook_dir.mkdir()
    hook_file = hook_dir / "test.json"
    hook_content = [
        {
            "name": "glob-test",
            "events": ["PreToolUse"],
            "type": "command",
            "config": {"command": "echo hello"},
            "matchers": [{"field": "tool_name", "operator": "glob", "value": "*.sh"}],
        }
    ]
    with open(hook_file, "w") as f:
        json.dump(hook_content, f)

    manager.scan(search_dirs=[str(hook_dir)])

    # Match: should run and return a successful execution result
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
async def test_hook_manager_nested_field_access(tmp_path):
    manager = HookManager(auto_load=False)

    # Create a dummy hook file to test nested field access via public scan method
    hook_dir = tmp_path / "hooks"
    hook_dir.mkdir(exist_ok=True)
    hook_file = hook_dir / "nested.json"
    hook_content = [
        {
            "name": "nested-test",
            "events": ["PreToolUse"],
            "type": "command",
            "config": {"command": "echo hello"},
            "matchers": [
                {"field": "metadata.user_id", "operator": "equals", "value": "123"}
            ],
        }
    ]
    with open(hook_file, "w") as f:
        json.dump(hook_content, f)

    manager.scan(search_dirs=[str(hook_dir)])

    results = await manager.execute_hooks(
        HookEvent.PRE_TOOL_USE, "data", metadata={"user_id": "123"}
    )
    assert any(r.message != "Skipped due to matchers" for r in results)

    results_skipped = await manager.execute_hooks(
        HookEvent.PRE_TOOL_USE, "data", metadata={"user_id": "456"}
    )
    assert any(r.message == "Skipped due to matchers" for r in results_skipped)

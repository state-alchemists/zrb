import json

import pytest

from zrb.llm.hook.interface import HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent


@pytest.fixture
def hook_manager():
    return HookManager(auto_load=False)


async def check_match(tmp_path, matchers, context_data):
    """Helper to verify if matchers work using public scan + execute_hooks."""
    manager = HookManager(auto_load=False)

    hook_dir = tmp_path / "hooks"
    if hook_dir.exists():
        import shutil

        shutil.rmtree(hook_dir)
    hook_dir.mkdir()

    hook_file = hook_dir / "test.json"
    hook_content = [
        {
            "name": "test-hook",
            "events": ["SessionStart"],
            "type": "command",
            "config": {"command": "echo matched"},
            "matchers": matchers,
        }
    ]
    with open(hook_file, "w") as f:
        json.dump(hook_content, f)

    manager.scan(search_dirs=[str(hook_dir)])

    # Extract event_data if present, otherwise use None
    data_to_pass = context_data.copy()
    event_data = data_to_pass.pop("event_data", None)

    # Pass context_data as kwargs so they populate HookContext attributes
    results = await manager.execute_hooks(
        HookEvent.SESSION_START, event_data, **data_to_pass
    )
    # If the hook matched, it should have been executed and returned a result that isn't "Skipped due to matchers"
    for result in results:
        if result.message != "Skipped due to matchers":
            return True
    return False


@pytest.mark.asyncio
async def test_evaluate_matchers_equals(tmp_path):
    # Match
    matchers = [{"field": "event_data.tool", "operator": "equals", "value": "bash"}]
    assert (
        await check_match(tmp_path, matchers, {"event_data": {"tool": "bash"}}) is True
    )

    # No Match
    matchers = [{"field": "event_data.tool", "operator": "equals", "value": "python"}]
    assert (
        await check_match(tmp_path, matchers, {"event_data": {"tool": "bash"}}) is False
    )


@pytest.mark.asyncio
async def test_evaluate_matchers_not_equals(tmp_path):
    # Match
    matchers = [
        {"field": "event_data.tool", "operator": "not_equals", "value": "python"}
    ]
    assert (
        await check_match(tmp_path, matchers, {"event_data": {"tool": "bash"}}) is True
    )

    # No Match
    matchers = [{"field": "event_data.tool", "operator": "not_equals", "value": "bash"}]
    assert (
        await check_match(tmp_path, matchers, {"event_data": {"tool": "bash"}}) is False
    )


@pytest.mark.asyncio
async def test_evaluate_matchers_contains(tmp_path):
    # Match
    matchers = [{"field": "prompt", "operator": "contains", "value": "world"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is True

    # No Match
    matchers = [{"field": "prompt", "operator": "contains", "value": "mars"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_starts_with(tmp_path):
    # Match
    matchers = [{"field": "prompt", "operator": "starts_with", "value": "hello"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is True

    # No Match
    matchers = [{"field": "prompt", "operator": "starts_with", "value": "world"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_ends_with(tmp_path):
    # Match
    matchers = [{"field": "prompt", "operator": "ends_with", "value": "world"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is True

    # No Match
    matchers = [{"field": "prompt", "operator": "ends_with", "value": "hello"}]
    assert await check_match(tmp_path, matchers, {"prompt": "hello world"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_regex(tmp_path):
    # Match
    matchers = [
        {"field": "prompt", "operator": "regex", "value": "error: .* not found"}
    ]
    assert (
        await check_match(tmp_path, matchers, {"prompt": "error: file not found"})
        is True
    )

    # No Match
    matchers = [{"field": "prompt", "operator": "regex", "value": "^success"}]
    assert (
        await check_match(tmp_path, matchers, {"prompt": "error: file not found"})
        is False
    )


@pytest.mark.asyncio
async def test_evaluate_matchers_glob(tmp_path):
    # Match
    matchers = [{"field": "tool_name", "operator": "glob", "value": "*.py"}]
    assert await check_match(tmp_path, matchers, {"tool_name": "script.py"}) is True

    # No Match
    matchers = [{"field": "tool_name", "operator": "glob", "value": "*.js"}]
    assert await check_match(tmp_path, matchers, {"tool_name": "script.py"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_case_sensitivity(tmp_path):
    # Case Insensitive Match
    matchers = [
        {
            "field": "prompt",
            "operator": "equals",
            "value": "hello world",
            "case_sensitive": False,
        }
    ]
    assert await check_match(tmp_path, matchers, {"prompt": "Hello World"}) is True

    # Case Sensitive Match Fail
    matchers = [
        {
            "field": "prompt",
            "operator": "equals",
            "value": "hello world",
            "case_sensitive": True,
        }
    ]
    assert await check_match(tmp_path, matchers, {"prompt": "Hello World"}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_nested_field_missing(tmp_path):
    # Field missing
    matchers = [
        {"field": "event_data.missing_key", "operator": "equals", "value": "value"}
    ]
    assert await check_match(tmp_path, matchers, {"event_data": {}}) is False


@pytest.mark.asyncio
async def test_evaluate_matchers_multiple(tmp_path):
    # All match
    matchers = [
        {"field": "tool_name", "operator": "equals", "value": "bash"},
        {"field": "prompt", "operator": "contains", "value": "rm"},
    ]
    assert (
        await check_match(tmp_path, matchers, {"tool_name": "bash", "prompt": "rm -rf"})
        is True
    )

    # One fails
    matchers = [
        {"field": "tool_name", "operator": "equals", "value": "bash"},
        {"field": "prompt", "operator": "contains", "value": "safe_command"},
    ]
    assert (
        await check_match(tmp_path, matchers, {"tool_name": "bash", "prompt": "rm -rf"})
        is False
    )

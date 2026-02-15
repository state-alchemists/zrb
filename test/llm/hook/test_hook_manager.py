import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.schema import (
    AgentHookConfig,
    CommandHookConfig,
    HookConfig,
    MatcherConfig,
    PromptHookConfig,
)
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator


@pytest.fixture
def manager():
    return HookManager(auto_load=False)


def test_get_field_value(manager):
    context = MagicMock(spec=HookContext)
    context.metadata = {"project": {"name": "zrb"}}
    context.event_data = "data"

    assert manager._get_field_value(context, "metadata.project.name") == "zrb"
    assert manager._get_field_value(context, "event_data") == "data"
    assert manager._get_field_value(context, "non_existent") is None
    assert manager._get_field_value(context, "metadata.none") is None


def test_evaluate_matchers(manager):
    context = MagicMock(spec=HookContext)
    context.tool_name = "Read"

    # Equals
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.EQUALS, value="Read"
    )
    assert manager._evaluate_matchers([matcher], context) is True

    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.EQUALS, value="Write"
    )
    assert manager._evaluate_matchers([matcher], context) is False

    # Not Equals
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.NOT_EQUALS, value="Write"
    )
    assert manager._evaluate_matchers([matcher], context) is True

    # Contains
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.CONTAINS, value="ea"
    )
    assert manager._evaluate_matchers([matcher], context) is True

    # Starts With
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.STARTS_WITH, value="Re"
    )
    assert manager._evaluate_matchers([matcher], context) is True

    # Ends With
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.ENDS_WITH, value="ad"
    )
    assert manager._evaluate_matchers([matcher], context) is True

    # Regex
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.REGEX, value="R.a"
    )
    assert manager._evaluate_matchers([matcher], context) is True

    # Glob
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.GLOB, value="R*d"
    )
    assert manager._evaluate_matchers([matcher], context) is True


@pytest.mark.asyncio
async def test_hook_priority(manager):
    async def low_priority_hook(ctx):
        return HookResult(success=True, output="low")

    async def high_priority_hook(ctx):
        return HookResult(success=True, output="high")

    manager.register(
        low_priority_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="low",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=10,
        ),
    )
    manager.register(
        high_priority_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="high",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=100,
        ),
    )

    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert len(results) == 2
    assert results[0].message == "high"
    assert results[1].message == "low"


@pytest.mark.asyncio
async def test_hook_blocking_exit_code_2(manager):
    executed = []

    async def blocking_hook(ctx):
        executed.append("blocking")
        return HookResult.block("Blocked by hook")

    async def subsequent_hook(ctx):
        executed.append("subsequent")
        return HookResult(success=True)

    manager.register(
        blocking_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="blocking",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=100,
        ),
    )
    manager.register(
        subsequent_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="subsequent",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=10,
        ),
    )

    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert "blocking" in executed
    assert len(results) == 1
    assert results[0].exit_code == 2


@pytest.mark.asyncio
async def test_hook_continue_false(manager):
    executed = []

    async def stop_hook(ctx):
        executed.append("stop")
        return HookResult(success=True, modifications={"continue": False})

    async def subsequent_hook(ctx):
        executed.append("subsequent")
        return HookResult(success=True)

    manager.register(
        stop_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="stop",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=100,
        ),
    )
    manager.register(
        subsequent_hook,
        events=[HookEvent.SESSION_START],
        config=HookConfig(
            name="subsequent",
            events=[],
            type=HookType.COMMAND,
            config=CommandHookConfig(command=""),
            priority=10,
        ),
    )

    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert "stop" in executed
    assert len(results) == 1
    assert results[0].continue_execution is False


@pytest.mark.asyncio
async def test_execute_hooks_simple(manager):
    async def my_hook(ctx):
        return HookResult(success=True, output="Hello")

    manager.register(my_hook, events=[HookEvent.SESSION_START])

    results = await manager.execute_hooks_simple(HookEvent.SESSION_START, {})
    assert len(results) == 1
    assert results[0].success
    assert results[0].output == "Hello"


def test_parse_claude_format(manager):
    claude_config = {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "matcher": ".*test.*",
                    "hooks": [{"type": "command", "command": "echo hello"}],
                }
            ]
        }
    }

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.return_value.hex = "12345678"
        manager._parse_claude_format(claude_config, "test_source")

    assert HookEvent.USER_PROMPT_SUBMIT in manager._hooks
    assert len(manager._hooks[HookEvent.USER_PROMPT_SUBMIT]) == 1
    hook = manager._hooks[HookEvent.USER_PROMPT_SUBMIT][0]
    config = manager._hook_to_config[hook]
    assert config.type == HookType.COMMAND
    assert config.config.command == "echo hello"
    assert len(config.matchers) == 1
    assert config.matchers[0].field == "prompt"
    assert config.matchers[0].value == ".*test.*"


def test_scan_and_load_from_path(manager, tmp_path):
    # Create a dummy hook file
    hook_dir = tmp_path / "hooks"
    hook_dir.mkdir()
    hook_file = hook_dir / "test.json"
    hook_content = [
        {
            "name": "test-hook",
            "events": ["SessionStart"],
            "type": "command",
            "config": {"command": "echo hello"},
        }
    ]
    with open(hook_file, "w") as f:
        json.dump(hook_content, f)

    manager.scan(search_dirs=[str(hook_dir)])

    assert HookEvent.SESSION_START in manager._hooks
    assert len(manager._hooks[HookEvent.SESSION_START]) == 1
    hook = manager._hooks[HookEvent.SESSION_START][0]
    config = manager._hook_to_config[hook]
    assert config.name == "test-hook"
    assert config.config.command == "echo hello"


def test_load_hooks_from_python(manager, tmp_path):
    # Create a dummy python hook file
    python_hook_file = tmp_path / "test.hook.py"
    python_content = """
from zrb.llm.hook.types import HookEvent
from zrb.llm.hook.interface import HookResult

async def my_hook(ctx):
    return HookResult(success=True)

def register(manager):
    manager.register(my_hook, events=[HookEvent.SESSION_START])
"""
    with open(python_hook_file, "w") as f:
        f.write(python_content)

    manager._load_from_path(python_hook_file)

    assert HookEvent.SESSION_START in manager._hooks
    assert len(manager._hooks[HookEvent.SESSION_START]) == 1


def test_get_field_value_nested_dict(manager):
    context = MagicMock(spec=HookContext)
    context.metadata = {"a": {"b": {"c": 1}}}
    assert manager._get_field_value(context, "metadata.a.b.c") == 1
    assert manager._get_field_value(context, "metadata.a.x") is None


def test_evaluate_matchers_regex_error(manager):
    context = MagicMock(spec=HookContext)
    context.tool_name = "Read"
    matcher = MatcherConfig(
        field="tool_name", operator=MatcherOperator.REGEX, value="["
    )  # Invalid regex
    assert manager._evaluate_matchers([matcher], context) is False


@pytest.mark.asyncio
async def test_execute_hooks_exception(manager):
    async def failing_hook(ctx):
        raise ValueError("Hook failed")

    manager.register(failing_hook, events=[HookEvent.SESSION_START])
    results = await manager.execute_hooks(HookEvent.SESSION_START, {})
    assert len(results) == 1
    assert results[0].success is False
    assert "Hook failed" in results[0].message


def test_load_file_yaml(manager, tmp_path):
    yaml_file = tmp_path / "hooks.yaml"
    yaml_content = [
        {
            "name": "yaml-hook",
            "events": ["SessionStart"],
            "type": "command",
            "config": {"command": "echo yaml"},
        }
    ]
    with open(yaml_file, "w") as f:
        yaml.dump(yaml_content, f)

    manager._load_file(yaml_file)
    assert HookEvent.SESSION_START in manager._hooks
    assert len(manager._hooks[HookEvent.SESSION_START]) == 1


def test_load_file_invalid_json(manager, tmp_path):
    json_file = tmp_path / "invalid.json"
    with open(json_file, "w") as f:
        f.write("{invalid: json}")

    # Should not raise exception, just log error
    manager._load_file(json_file)
    assert len(manager._hooks) == 0


def test_create_hook_config_types(manager):
    prompt_data = {
        "name": "p-hook",
        "events": ["SessionStart"],
        "type": "prompt",
        "config": {"user_prompt_template": "hi"},
    }
    config = manager._create_hook_config(prompt_data)
    assert config.type == HookType.PROMPT
    assert config.config.user_prompt_template == "hi"

    agent_data = {
        "name": "a-hook",
        "events": ["SessionStart"],
        "type": "agent",
        "config": {"system_prompt": "be nice"},
    }
    config = manager._create_hook_config(agent_data)
    assert config.type == HookType.AGENT
    assert config.config.system_prompt == "be nice"


@pytest.mark.asyncio
async def test_command_hook_execution(manager):
    config = CommandHookConfig(command='echo \'{"success": true, "foo": "bar"}\'')
    hook = manager._create_command_hook(config)
    context = HookContext(event=HookEvent.SESSION_START, event_data={})
    result = await hook(context)
    assert result.success is True
    assert result.modifications == {"success": True, "foo": "bar"}


@pytest.mark.asyncio
async def test_command_hook_blocking(manager):
    # Exit code 2 means block
    config = CommandHookConfig(
        command='echo \'{"reason": "blocked by script"}\'; exit 2'
    )
    hook = manager._create_command_hook(config)
    context = HookContext(event=HookEvent.SESSION_START, event_data={})
    result = await hook(context)
    assert result.success is False
    assert result.should_stop is True
    assert result.modifications["reason"] == "blocked by script"


@pytest.mark.asyncio
async def test_hydrate_hook_async(manager):
    config = HookConfig(
        name="async-hook",
        events=[HookEvent.SESSION_START],
        type=HookType.COMMAND,
        config=CommandHookConfig(command="sleep 0.1; echo hello"),
        is_async=True,
    )
    hook = manager._hydrate_hook(config)
    context = HookContext(event=HookEvent.SESSION_START, event_data={})
    result = await hook(context)
    assert result.output == "Async execution started"

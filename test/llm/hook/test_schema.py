from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.schema import CommandHookConfig, HookConfig, HookEvent, HookType


def test_valid_command_hook_config():
    config_data = {
        "name": "test-hook",
        "events": ["SessionStart"],
        "type": "command",
        "config": {"command": "echo hello", "shell": True},
    }
    # hook_manager has a helper to create config from dict
    config = hook_manager._create_hook_config(config_data)
    assert config.name == "test-hook"
    assert config.type == HookType.COMMAND
    assert isinstance(config.config, CommandHookConfig)
    assert config.config.command == "echo hello"
    assert HookEvent.SESSION_START in config.events


def test_invalid_hook_config():
    config_data = {
        "name": "test-hook",
        # Missing events - this will raise KeyError in our manual parser
        "type": "command",
        "config": {"command": "echo hello"},
    }
    try:
        hook_manager._create_hook_config(config_data)
        assert False, "Should have raised KeyError"
    except KeyError:
        pass

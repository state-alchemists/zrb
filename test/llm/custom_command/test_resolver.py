"""Tests for llm/custom_command/resolver.py."""

from zrb.llm.custom_command.custom_command import CustomCommand
from zrb.llm.custom_command.resolver import (
    resolve_custom_command,
    resolve_custom_commands,
)


def test_resolve_custom_commands_passes_through_plain_objects():
    a = CustomCommand("/a", "prompt-a", args=[])
    b = CustomCommand("/b", "prompt-b", args=[])
    out = resolve_custom_commands([a, b])
    assert out == [a, b]


def test_resolve_custom_commands_calls_factory_returning_single():
    cmd = CustomCommand("/c", "prompt-c", args=[])
    out = resolve_custom_commands([lambda: cmd])
    assert out == [cmd]


def test_resolve_custom_commands_calls_factory_returning_list():
    cmd_a = CustomCommand("/a", "p", args=[])
    cmd_b = CustomCommand("/b", "p", args=[])
    out = resolve_custom_commands([lambda: [cmd_a, cmd_b]])
    assert out == [cmd_a, cmd_b]


def test_resolve_custom_command_no_slash_returns_none():
    assert resolve_custom_command("hello world", []) is None


def test_resolve_custom_command_empty_after_split_returns_none():
    """A bare slash with no command name resolves to nothing."""
    cmd = CustomCommand("/foo", "do foo", args=[])
    assert resolve_custom_command("/bar", [cmd]) is None


def test_resolve_custom_command_with_unmatched_quoting_returns_none():
    """shlex.split raising must be swallowed, not crashed on."""
    # Unbalanced quote causes shlex.split to raise ValueError
    assert resolve_custom_command('/cmd "unbalanced', []) is None


def test_resolve_custom_command_matches_and_returns_prompt():
    cmd = CustomCommand("/greet", "Hello $name!", args=["name"])
    out = resolve_custom_command("/greet alice", [cmd])
    assert out == "Hello alice!"


def test_resolve_custom_command_joins_residue_args():
    """Extra positional args get joined into the last declared arg."""
    cmd = CustomCommand(
        "/say",
        "${who} says: ${msg}",
        args=["who", "msg"],
    )
    out = resolve_custom_command("/say bob hello there friends", [cmd])
    assert out == "bob says: hello there friends"


def test_resolve_custom_command_missing_args_default_to_empty():
    cmd = CustomCommand("/x", "[${a}|${b}]", args=["a", "b"])
    out = resolve_custom_command("/x only-a", [cmd])
    assert out == "[only-a|]"

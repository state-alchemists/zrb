"""Tests for llm/custom_command/resolver.py."""

from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.custom_command.custom_command import CustomCommand
from zrb.llm.custom_command.resolver import (
    CustomCommandOutcome,
    get_custom_command_match,
    resolve_custom_command,
    resolve_custom_commands,
    run_custom_command,
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
    """shlex.split raising must not crash, and must not match a stranger."""
    # Unbalanced quote causes shlex.split to raise ValueError
    assert resolve_custom_command('/cmd "unbalanced', []) is None


def test_resolve_custom_command_with_unmatched_quoting_still_dispatches():
    """A typo'd quote must not silently demote a command to a plain message.

    shlex.split raises on the unbalanced quote; the whitespace fallback still
    finds `/greet`, so the user sees their command run rather than watching it
    reach the model verbatim.
    """
    cmd = CustomCommand("/greet", "Hello ${name}!", args=["name"])
    assert resolve_custom_command('/greet "alice', [cmd]) == 'Hello "alice!'


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


def test_run_custom_command_returns_prompt_when_handle_declines():
    cmd = CustomCommand("/greet", "Say hi to $name", args=["name"])
    outcome = run_custom_command("/greet Ann", [cmd], None)
    assert outcome == CustomCommandOutcome(prompt="Say hi to Ann", reply=None)


def test_run_custom_command_runs_action_instead_of_prompting():
    calls = []
    cmd = ActionCommand(
        "/toggle", lambda kwargs, ui: calls.append(kwargs) or "on", args=["mode"]
    )
    outcome = run_custom_command("/toggle fast", [cmd], None)
    assert outcome == CustomCommandOutcome(prompt=None, reply="on")
    assert calls == [{"mode": "fast"}]


def test_run_custom_command_action_returning_none_is_still_handled():
    cmd = ActionCommand("/quiet", lambda kwargs, ui: None)
    assert run_custom_command("/quiet", [cmd], None) == CustomCommandOutcome(
        prompt=None, reply=""
    )


def test_run_custom_command_accepts_duck_typed_command_without_handle():
    class Legacy:
        command = "/old"
        description = "old"
        args: list[str] = []

        def get_prompt(self, kwargs):
            return "legacy prompt"

    outcome = run_custom_command("/old", [Legacy()], None)  # type: ignore[list-item]
    assert outcome is not None and outcome.prompt == "legacy prompt"


def test_run_custom_command_no_match_returns_none():
    assert (
        run_custom_command("/nope", [ActionCommand("/toggle", lambda k, ui: "x")], None)
        is None
    )


def test_get_custom_command_match_does_not_run_the_action():
    calls = []
    cmd = ActionCommand("/toggle", lambda kwargs, ui: calls.append(1))
    match = get_custom_command_match("/toggle", [cmd])
    assert match == (cmd, {})
    assert calls == []


def test_action_command_description_lists_args():
    cmd = ActionCommand("/set", lambda k, ui: None, args=["key", "value"])
    assert cmd.description == "/set <key> <value>"
    assert cmd.get_prompt({}) == ""
    assert (
        ActionCommand("/x", lambda k, ui: None, description="Do x").description
        == "Do x"
    )

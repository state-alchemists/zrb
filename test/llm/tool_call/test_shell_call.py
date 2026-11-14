"""What counts as a shell call, and where its command lives (ADR-0141).

The shape is shared: the approval formatter, the read-only auto-approve policy
and the shell judge all have to recognise the same call, so the questions are
answered in one place and pinned here.
"""

from zrb.llm.agent.types import ToolCallPart
from zrb.llm.tool_call.shell_call import (
    is_shell_call,
    shell_command,
    shell_command_args,
    is_sandbox_off,
)


def _call(command: object = "ls", tool_name: str = "Shell") -> ToolCallPart:
    """A call exactly as the approval cascade receives one: a bare
    `ToolCallPart`, carrying no capability metadata."""
    return ToolCallPart(
        tool_name=tool_name, args={"command": command}, tool_call_id="call-1"
    )


def test_a_bare_deferred_call_is_a_shell_command():
    """The regression the review of #908 caught: a deferred `ToolCallPart`
    carries no capability metadata, so a gate that asks `tool_capability` never
    matches and the judge silently never runs. The name is the only handle."""
    call = _call("ls")
    assert is_shell_call(call)
    args = shell_command_args(call)
    assert args is not None
    assert shell_command(args) == "ls"


def test_another_tool_is_not_a_shell_call():
    other = _call("ls", tool_name="RunZrbTask")
    assert not is_shell_call(other)
    assert shell_command_args(other) is None


def test_a_call_with_nothing_to_run_is_not_a_shell_command():
    assert shell_command_args(_call("")) is None
    assert shell_command_args(_call("   ")) is None
    assert shell_command_args(_call(None)) is None
    assert shell_command_args(_call(42)) is None


def test_args_that_are_not_an_object_are_not_a_shell_command():
    """`parse_tool_args` hands back whatever the JSON said; a list is not a
    command, and reading `.get` off it would raise inside the cascade."""
    call = ToolCallPart(tool_name="Shell", args='["ls"]', tool_call_id="c")
    assert shell_command_args(call) is None


def test_the_sandbox_flag_is_read_the_same_way_by_every_caller():
    assert is_sandbox_off({"command": "ls", "dangerously_skip_sandbox": True})
    assert not is_sandbox_off({"command": "ls"})

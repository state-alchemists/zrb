"""What counts as a shell call, and where its command lives (ADR-0141).

The shape is shared: the approval formatter, the read-only auto-approve policy
and the shell judge all have to recognise the same call, so the questions are
answered in one place and pinned here.
"""

import re
from pathlib import Path

from zrb.llm.agent.types import ToolCallPart
from zrb.llm.capabilities.tool_call.shell_call import (
    is_sandbox_off,
    is_shell_call,
    shell_command,
    shell_command_args,
)

_REPO_ROOT = Path(__file__).parents[3]
_SHELL_CALL = _REPO_ROOT / "src" / "zrb" / "llm" / "tool_call" / "shell_call.py"
#: The argument name as a quoted token — a reader of the shape, not the
#: identifier a signature declares or a sentence that mentions it.
_QUOTED_NAME = re.compile(r"""["']dangerously_skip_sandbox["']""")


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


def test_the_sandbox_flag_name_is_not_typed_anywhere_else():
    """One name, one reader — the reason this module exists.

    The formatter, the auto-approve policy, the sandbox gate and the deferred
    cascade each compared against the string itself, so the name lived in five
    places and one of them was a file that already imported `is_sandbox_off`
    sixty lines below. A caller added later would not have inherited the check
    at all, and nothing would have said so.
    """
    offenders = sorted(
        str(path.relative_to(_REPO_ROOT))
        for path in (_REPO_ROOT / "src" / "zrb").rglob("*.py")
        if path != _SHELL_CALL and _QUOTED_NAME.search(path.read_text("utf-8"))
    )
    assert offenders == [], (
        "Read the sandbox-escape argument through `is_sandbox_off` "
        "(`zrb.llm.capabilities.tool_call.shell_call`), not by name: " + ", ".join(offenders)
    )

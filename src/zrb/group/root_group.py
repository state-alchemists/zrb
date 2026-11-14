"""The root group `zrb <group> <task>` addresses, held where both sides can see it.

The tree is built by the CLI — `runner/cli.py` creates the `cli` singleton and
the built-in tasks hang off it — while one agent tool reads it to list what zrb
can do (`llm/tool/zrb_task.py`). The engine must not import the runner to reach
it: the tool registry is built on every agent run, in embedders too, and
importing the CLI there drags the server stack (`web_auth_config`, `Session`,
`session_state_logger`, `make_task`) into every process that builds an agent.
So the runner registers its group here when it creates it, and the engine reads
it back — the same seam `zrb.llm.shared.agent_state` uses for the current UI.

This is a handover, not an extension point. `run_zrb_task` executes the `zrb`
command in a child process, so a tree registered here and nowhere else would be
listed by one tool and unrunnable through the other; register your own tree
only when the `zrb` command can build it too. In a process that never loads the
CLI nothing is registered, and the listing tool says so plainly instead of
walking a tree the caller never chose.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zrb.group.any_group import AnyGroup

_root_group: "AnyGroup | None" = None


def set_root_group(group: "AnyGroup | None") -> None:
    """Register *group* as the tree the task tools walk.

    Passing ``None`` clears it, which is what a test does to check the
    unregistered answer; a process registers once, when it builds the tree.
    """
    global _root_group
    _root_group = group


def get_root_group() -> "AnyGroup | None":
    """The registered root group, or ``None`` when nothing registered one."""
    return _root_group

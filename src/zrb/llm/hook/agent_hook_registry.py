"""Registration seam for the `HookType.AGENT` hook builder.

`hook/manager.py` must build an agent-type hook without importing the agent
subsystem directly: that subsystem (`agent/common.py`) already depends on
`hook.manager` to fire PreToolUse/PostToolUse, so a direct import back would
recreate the cycle this module exists to avoid. `zrb.llm.agent` installs the
real builder here as a side effect of its own package import (see
`agent/hook_agent.py`); `hook/manager.py` only ever reads it back through
`get_agent_hook_builder`.

Kept dependency-free (stdlib + TYPE_CHECKING-only hook types), the same
shape `zrb.llm.factory_resolver` already uses to let sibling modules share a
helper without risking an import cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from zrb.llm.hook.interface import HookCallable
    from zrb.llm.hook.schema import AgentHookConfig

AgentHookBuilder = Callable[["AgentHookConfig"], "HookCallable"]

_builder: "AgentHookBuilder | None" = None


def register_agent_hook_builder(builder: "AgentHookBuilder") -> None:
    """Install the real `HookType.AGENT` builder. Called once, by `zrb.llm.agent`."""
    global _builder
    _builder = builder


def get_agent_hook_builder() -> "AgentHookBuilder | None":
    """The registered builder, or `None` if `zrb.llm.agent` was never imported
    in this process (e.g. a hook-only test that never touches the agent
    subsystem)."""
    return _builder

"""Registration seam for the `HookType.AGENT` hook builder.

`zrb.llm.agent` depends on `hook.manager`, so the manager cannot import the
agent subsystem back; `zrb.llm.agent` registers the real builder here
(`agent/hook_agent.py`) instead. Keep this module dependency-free.
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
    """The registered builder, or `None` if `zrb.llm.agent` was never used."""
    return _builder

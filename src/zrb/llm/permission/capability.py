"""Per-tool capability tags.

Generalizes the existing ``zrb_is_delegate_tool`` attribute pattern: a tool
optionally carries a ``zrb_capability`` tag describing what kind of side effect
it has. Untagged tools resolve to ``UNKNOWN`` and are treated conservatively by
each consumer (e.g. denied in read-only plan mode), so leaving a third-party or
MCP tool untagged is safe-by-default.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

_CAPABILITY_ATTR = "zrb_capability"


class Capability(str, Enum):
    READ = "read"  # pure reads: Read, LS, Glob, Grep, Analyze*, SearchJournal
    EDIT = "edit"  # filesystem mutation: Write, Edit, RM, MV, Enter/ExitWorktree
    EXECUTE = "execute"  # arbitrary side effects: Bash, RunZrbTask
    NETWORK = "network"  # outbound network: WebSearch, WebFetch
    DELEGATE = "delegate"  # spawns sub-agents
    META = "meta"  # harness control, no external effect: todos, skills, AskUser
    UNKNOWN = "unknown"  # untagged — treated conservatively by consumers


def tag(fn: Any, capability: Capability) -> Any:
    """Attach a capability tag to a tool callable and return it (chainable)."""
    setattr(fn, _CAPABILITY_ATTR, capability)
    return fn


def tool_capability(tool: Any) -> Capability:
    """Best-effort capability of a tool.

    Resolution order:
    1. explicit ``zrb_capability`` tag (on the tool or its underlying function),
    2. ``DELEGATE`` if the tool carries ``zrb_is_delegate_tool``,
    3. ``UNKNOWN``.
    """
    cap = getattr(tool, _CAPABILITY_ATTR, None)
    if isinstance(cap, Capability):
        return cap
    fn = getattr(tool, "function", None)
    if fn is not None:
        cap = getattr(fn, _CAPABILITY_ATTR, None)
        if isinstance(cap, Capability):
            return cap
    if getattr(tool, "zrb_is_delegate_tool", False) or (
        fn is not None and getattr(fn, "zrb_is_delegate_tool", False)
    ):
        return Capability.DELEGATE
    return Capability.UNKNOWN

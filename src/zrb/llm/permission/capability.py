"""Per-tool capability tags.

Untagged tools resolve to ``UNKNOWN``, which consumers treat conservatively
(e.g. denied in plan mode).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

CAPABILITY_ATTR = "zrb_capability"


class Capability(str, Enum):
    READ = "read"  # pure reads: Read, LS, Glob, Grep, Analyze*, SearchJournal
    EDIT = "edit"  # filesystem mutation: Write, Edit, RM, MV, Enter/ExitWorktree
    EXECUTE = "execute"  # arbitrary side effects: Shell, RunZrbTask
    NETWORK = "network"  # outbound network: WebSearch, WebFetch
    DELEGATE = "delegate"  # spawns sub-agents
    META = "meta"  # harness control, no external effect: todos, skills, AskUser
    UNKNOWN = "unknown"  # untagged — treated conservatively by consumers


def tag(fn: Any, capability: Capability) -> Any:
    """Attach a capability tag to a tool callable and return it (chainable)."""
    setattr(fn, CAPABILITY_ATTR, capability)
    return fn


def capability_metadata(capability: Capability) -> dict[str, Capability]:
    """Build a ``ToolDefinition.metadata`` dict carrying ``capability``.

    pydantic-ai's toolset dispatch sees only a ``ToolsetTool``, where a
    ``tag()`` on the original callable is lost but ``metadata`` survives.
    """
    return {CAPABILITY_ATTR: capability}


def tool_capability(tool: Any) -> Capability:
    """Best-effort capability of a tool.

    Order: ``zrb_capability`` tag on the tool or its function, the tag in
    ``tool_def.metadata``, ``DELEGATE`` for ``zrb_is_delegate_tool``, else
    ``UNKNOWN``.
    """
    cap = getattr(tool, CAPABILITY_ATTR, None)
    if isinstance(cap, Capability):
        return cap
    fn = getattr(tool, "function", None)
    if fn is not None:
        cap = getattr(fn, CAPABILITY_ATTR, None)
        if isinstance(cap, Capability):
            return cap
    tool_def = getattr(tool, "tool_def", None)
    metadata = getattr(tool_def, "metadata", None) if tool_def is not None else None
    if metadata:
        cap = metadata.get(CAPABILITY_ATTR)
        if isinstance(cap, Capability):
            return cap
    if getattr(tool, "zrb_is_delegate_tool", False) or (
        fn is not None and getattr(fn, "zrb_is_delegate_tool", False)
    ):
        return Capability.DELEGATE
    return Capability.UNKNOWN

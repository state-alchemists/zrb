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

    pydantic-ai's per-call dispatch (``SafeToolsetWrapper.call_tool`` in
    ``agent/common.py``) only ever sees a ``ToolsetTool``, which has no
    ``.function`` and no arbitrary attributes — a ``tag()`` set on the
    original callable does not survive into that layer. ``ToolDefinition.metadata``
    does, so ``_wrap_tool`` re-tags the capability here when it rebuilds the
    ``Tool``.
    """
    return {CAPABILITY_ATTR: capability}


def tool_capability(tool: Any) -> Capability:
    """Best-effort capability of a tool.

    Resolution order:
    1. explicit ``zrb_capability`` tag (on the tool or its underlying function),
    2. the same tag carried as ``ToolDefinition.metadata`` (the shape a
       ``ToolsetTool`` — e.g. what pydantic-ai's toolset dispatch hands the
       outer gate — exposes it in),
    3. ``DELEGATE`` if the tool carries ``zrb_is_delegate_tool``,
    4. ``UNKNOWN``.
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

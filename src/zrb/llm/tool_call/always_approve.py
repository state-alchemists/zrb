"""Registry of tools that are intrinsically auto-approved.

Some tools *are* the user interaction (e.g. ``AskUserQuestion``): gating them
behind a tool-approval prompt is meaningless — it inserts a redundant "Allow
tool execution?" step that renders *before* the real question does, so the user
is asked to approve a tool whose purpose they cannot yet see.

Tools register here at definition time, so auto-approval travels with the tool
itself rather than depending on a per-runner policy list (e.g. the builtin
chat's ``auto_approve(...)`` registrations in ``builtin/llm/chat.py``). The
approval cascade (``agent/run/deferred_calls.py::_resolve_approval``) consults
this set first — Priority 0 — so the guarantee holds in every path: the main
agent, delegated sub-agents, and the web/API runner alike. See ADR-0062.

This module is an intentional dependency-free leaf so importing it can never
introduce an import cycle from the approval cascade or from tool definitions.
"""

from __future__ import annotations

_ALWAYS_AUTO_APPROVE: set[str] = set()


def register_always_auto_approve(*tool_names: str) -> None:
    """Mark tool(s), by LLM-visible name, as intrinsically auto-approved.

    Auto-approval then applies in every approval path, independent of any
    per-runner tool-policy list. Call this at tool-definition time.
    """
    _ALWAYS_AUTO_APPROVE.update(tool_names)


def is_always_auto_approve(tool_name: str) -> bool:
    """Whether ``tool_name`` is intrinsically auto-approved (never prompts)."""
    return tool_name in _ALWAYS_AUTO_APPROVE

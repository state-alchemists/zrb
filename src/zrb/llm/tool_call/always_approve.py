"""Registry of tools that are intrinsically auto-approved.

Some tools *are* the user interaction (e.g. ``AskUserQuestion``), so an
approval prompt before them is redundant. Tools register at definition time;
the approval cascade (``agent/run/deferred_calls.py``) checks this set first,
in every runner. Kept dependency-free to avoid import cycles.
"""

from __future__ import annotations

_ALWAYS_AUTO_APPROVE: set[str] = set()


def register_always_auto_approve(*tool_names: str) -> None:
    """Mark tool(s), by LLM-visible name, as intrinsically auto-approved."""
    _ALWAYS_AUTO_APPROVE.update(tool_names)


def is_always_auto_approve(tool_name: str) -> bool:
    """Whether ``tool_name`` is intrinsically auto-approved (never prompts)."""
    return tool_name in _ALWAYS_AUTO_APPROVE

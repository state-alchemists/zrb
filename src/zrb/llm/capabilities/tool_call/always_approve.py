"""Registries of tools that are approved without asking, at two strengths.

Some tools *are* the user interaction (``AskUserQuestion``). An approval prompt
before one would ask the user to approve talking to the user, so they register
as always-approved: the approval cascade (``agent/run/deferred_calls.py``)
checks that set first, above every rule, and no rule can stop it.

Others are the harness's own defaults. Their blast radius is bounded, and a
prompt on every call is friction that trains a user to answer without reading —
memory writes, re-reading a tool result the user already approved producing,
messaging a sub-agent we just started. Those register as default-approved: the
cascade checks that set *after* the permission policy, so a user's ``ask`` or
``deny`` rule still wins and a PreToolUse ``ask`` still forces the prompt.

Tools register next to the surface that ships them (``common_tools.py``), so
nothing here has to know which host is running. Kept dependency-free to avoid
import cycles.
"""

from __future__ import annotations

from collections.abc import Callable

_ALWAYS_AUTO_APPROVE: set[str] = set()

# Tool name -> a predicate over the call's arguments, or None for "any call".
_DEFAULT_AUTO_APPROVE: dict[str, Callable[[dict[str, object]], bool] | None] = {}


def register_always_auto_approve(*tool_names: str) -> None:
    """Mark tool(s), by LLM-visible name, as intrinsically auto-approved."""
    _ALWAYS_AUTO_APPROVE.update(tool_names)


def is_always_auto_approve(tool_name: str) -> bool:
    """Whether ``tool_name`` is intrinsically auto-approved (never prompts)."""
    return tool_name in _ALWAYS_AUTO_APPROVE


def register_default_auto_approve(*tool_names: str) -> None:
    """Mark tool(s) the harness approves unless a permission rule says otherwise."""
    for tool_name in tool_names:
        _DEFAULT_AUTO_APPROVE.setdefault(tool_name, None)


def register_default_auto_approve_if(
    tool_name: str, predicate: Callable[[dict[str, object]], bool]
) -> None:
    """Approve *tool_name* only for the calls *predicate* accepts.

    For a tool whose boundedness is an argument rather than the whole tool: an
    `LspRenameSymbol` dry run reports what it would do, and the same call
    without `dry_run` writes. A call whose arguments do not parse is not
    approved — the predicate never sees a dict it can trust, so the prompt stays.
    """
    _DEFAULT_AUTO_APPROVE[tool_name] = predicate


def is_default_auto_approve(
    tool_name: str, args: dict[str, object] | None = None
) -> bool:
    """Whether the harness approves this call by default (a rule may still ask)."""
    if tool_name not in _DEFAULT_AUTO_APPROVE:
        return False
    predicate = _DEFAULT_AUTO_APPROVE[tool_name]
    if predicate is None:
        return True
    return isinstance(args, dict) and predicate(args)

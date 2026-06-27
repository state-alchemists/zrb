"""Execution gates applied to every wrapped tool call.

Two independent gates sit in front of in-process tool execution, consulted by
the safe-wrappers in ``agent/common.py``:

* :func:`permission_gate` — enforces the *deny* outcome of the active
  ``PermissionPolicy`` (the allow/ask outcomes are handled by the approval
  layer; only deny is expressed here).
* :func:`sandbox_gate` — enforces the filesystem sandbox policy by inspecting
  path-like arguments.

Both return a blocked ``ToolReturn`` to short-circuit the call, or ``None`` to
let it proceed. ``None`` is the zero-cost default path (no policy / sandbox
disabled), so the common case is unaffected.
"""

from __future__ import annotations

from typing import Any

from zrb.llm.permission import (
    DENY,
    Capability,
    get_current_agent_mode,
    get_effective_policy,
)
from zrb.llm.sandbox import check_read, check_write, get_effective_sandbox_policy


def permission_gate(tool_name: str, capability: Any, args: dict[str, Any]) -> Any:
    """Return a blocked ``ToolReturn`` if the in-force policy denies this call.

    Returns ``None`` when nothing denies it (the default — no policy and
    ``AgentMode.BUILD`` → always ``None``, so the synchronous path is
    unchanged). Enforces the *deny* outcome that the approval layer (allow/ask)
    cannot express, without touching the deferred-request machinery.
    """
    # lazy: heavy third-party deferral
    from pydantic_ai import ToolReturn

    policy = get_effective_policy()
    if policy is None:
        return None
    if policy.decide(tool_name, capability, args) != DENY:
        return None
    mode = get_current_agent_mode().value
    return ToolReturn(
        return_value=None,
        content=(
            f"Blocked: '{tool_name}' is not permitted under the current "
            f"permission policy (mode: {mode}). "
            "[SYSTEM SUGGESTION]: this is a read-only / restricted context. "
            "Finish discovery, then call ExitPlanMode (if in plan mode) to "
            "present your plan for approval before making changes."  # fmt: skip
        ),
        metadata={"blocked": True},
    )


def sandbox_gate(tool_name: str, capability: Any, args: dict[str, Any]) -> Any:
    """Return a blocked ``ToolReturn`` if the sandbox FS policy denies this call.

    Returns ``None`` when the sandbox is disabled (the default — zero-cost
    path) or no path argument violates the policy. EXECUTE tools are not
    path-checked here: shell commands are contained by the OS-level sandbox
    layer, not by argument inspection.
    """
    # lazy: heavy third-party deferral
    from pydantic_ai import ToolReturn

    # Argument keys the sandbox gate treats as filesystem paths (subset of the
    # permission layer's _SALIENT_ARG_KEYS). Reads check every path-like arg;
    # writes additionally check them for EDIT/UNKNOWN tools ("src" is write-checked
    # because move_file deletes it; "dst" because it gets overwritten).
    _SANDBOX_READ_KEYS = ("path", "file_path", "file", "filename", "src")
    _SANDBOX_WRITE_KEYS = ("path", "file_path", "file", "filename", "src", "dst")

    policy = get_effective_sandbox_policy()
    if not policy.enabled:
        return None

    def _blocked(reason: str) -> Any:
        return ToolReturn(
            return_value=None,
            content=(
                f"Blocked by sandbox policy: {reason}. "
                "[SYSTEM SUGGESTION]: work within the project directory, or "
                "ask the user to extend the sandbox writable paths "
                "(LLM_SANDBOX_WRITABLE_PATHS) / adjust the deny list "
                "(LLM_SANDBOX_DENY_READ_PATHS)."
            ),
            metadata={"blocked": True},
        )

    if not policy.allow_escape and args.get("dangerously_skip_sandbox"):
        return _blocked(
            "dangerously_skip_sandbox was requested but escaping the sandbox "
            "is disabled in this deployment (LLM_SANDBOX_ALLOW_ESCAPE=false)"
        )

    cap_value = getattr(capability, "value", capability)
    if cap_value == Capability.EXECUTE.value:
        return None
    for key in _SANDBOX_READ_KEYS:
        value = args.get(key)
        if isinstance(value, str):
            error = check_read(value, policy)
            if error is not None:
                return _blocked(error)
    if cap_value in (Capability.EDIT.value, Capability.UNKNOWN.value):
        for key in _SANDBOX_WRITE_KEYS:
            value = args.get(key)
            if isinstance(value, str):
                error = check_write(value, policy)
                if error is not None:
                    return _blocked(error)
    return None

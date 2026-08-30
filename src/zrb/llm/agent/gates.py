"""Execution gates applied to every wrapped tool call.

Two independent gates sit in front of in-process tool execution, consulted by
the safe-wrappers in ``agent/common.py``:

* :func:`permission_gate` — enforces the *deny* outcome of the active
  ``PermissionPolicy`` (the allow/ask outcomes are handled by the approval
  layer; only deny is expressed here). Reads ``current_agent_mode`` fresh on
  every call (via ``get_effective_policy()``) because a mid-run mode switch
  (e.g. the model calling ``ExitPlanMode``) must take effect for the rest of
  that same run — this is why the policy stays ambient-read rather than
  moving to ``ctx.deps`` the way ``sandbox_gate`` does below.
* :func:`sandbox_gate` — enforces the filesystem sandbox policy by inspecting
  path-like arguments. Unlike the permission policy, the sandbox policy is
  fixed for a run's whole lifetime (nothing mutates it mid-run), so
  ``SafeToolsetWrapper.call_tool`` (the single chokepoint every tool call
  passes through) hands it ``ctx.deps`` — the policy `run_agent` resolved
  once and passed into `agent.run(deps=...)` — instead of a fresh ambient
  read. `ctx` is optional and falls back to the ambient read when omitted,
  for the one other caller (`create_safe_wrapper`'s own defense-in-depth gate
  call, redundant with the chokepoint above for real invocations) that has
  no `RunContext` to offer.

Both return a blocked ``ToolReturn`` to short-circuit the call, or ``None`` to
let it proceed. ``None`` is the zero-cost default path (no policy / sandbox
disabled), so the common case is unaffected.
"""

from __future__ import annotations

from typing import Any

from zrb.config.config import CFG
from zrb.llm.agent.tool_result import tool_return
from zrb.llm.permission import (
    DENY,
    Capability,
    get_current_agent_mode,
    get_effective_policy,
)
from zrb.llm.sandbox import check_read, check_write, get_effective_sandbox_policy
from zrb.llm.sandbox.policy import SandboxPolicy


def permission_gate(tool_name: str, capability: Any, args: dict[str, Any]) -> Any:
    """Return a blocked ``ToolReturn`` if the in-force policy denies this call.

    Returns ``None`` when nothing denies it (the default — no policy and
    ``AgentMode.BUILD`` → always ``None``, so the synchronous path is
    unchanged). Enforces the *deny* outcome that the approval layer (allow/ask)
    cannot express, without touching the deferred-request machinery.
    """
    policy = get_effective_policy()
    if policy is None:
        return None
    if policy.decide(tool_name, capability, args) != DENY:
        return None
    mode = get_current_agent_mode().value
    return tool_return(
        f"Blocked: '{tool_name}' is not permitted under the current "
        f"permission policy (mode: {mode}). "
        "[SYSTEM SUGGESTION]: this is a read-only / restricted context. "
        "Finish discovery, then call ExitPlanMode (if in plan mode) to "
        "present your plan for approval before making changes.",  # fmt: skip
        blocked=True,
    )


def sandbox_gate(
    tool_name: str, capability: Any, args: dict[str, Any], ctx: Any = None
) -> Any:
    """Return a blocked ``ToolReturn`` if the sandbox FS policy denies this call.

    Returns ``None`` when the sandbox is disabled (the default — zero-cost
    path) or no path argument violates the policy. EXECUTE tools are not
    path-checked here: shell commands are contained by the OS-level sandbox
    layer, not by argument inspection.

    ``ctx`` is a pydantic-ai ``RunContext`` (or ``None``): when given and
    ``ctx.deps`` is set, that's the policy `run_agent` resolved once for this
    run — read instead of the ambient ``ContextVar``, since it's the same
    value by construction and this is the one gate call site
    (`SafeToolsetWrapper.call_tool`) every real tool call passes through.
    """
    # Argument keys the sandbox gate treats as filesystem paths (subset of the
    # permission layer's _SALIENT_ARG_KEYS). Reads check every path-like arg;
    # writes additionally check them for EDIT/UNKNOWN tools ("src" is write-checked
    # because move_file deletes it; "dst" because it gets overwritten).
    # "worktree_path" is write-only (exit_worktree removes it) and only ever
    # matches ExitWorktree — EnterWorktree computes its destination internally,
    # never as a caller-supplied arg, so it can't be gated this way.
    _SANDBOX_READ_KEYS = ("path", "file_path", "file", "filename", "src")
    _SANDBOX_WRITE_KEYS = (
        "path",
        "file_path",
        "file",
        "filename",
        "src",
        "dst",
        "worktree_path",
    )

    # isinstance-checked, not just "is not None": a test double's `ctx` is
    # often a bare `MagicMock()`, whose `.deps` auto-vivifies into another
    # MagicMock rather than raising or returning None — falling back to the
    # ambient read for anything that isn't actually a SandboxPolicy avoids
    # silently gating on a mock's default (truthy) attribute behavior.
    deps = getattr(ctx, "deps", None)
    policy = deps if isinstance(deps, SandboxPolicy) else get_effective_sandbox_policy()
    if not policy.enabled:
        return None

    def _blocked(reason: str) -> Any:
        return tool_return(
            f"Blocked by sandbox policy: {reason}. "
            "[SYSTEM SUGGESTION]: work within the project directory, or "
            "ask the user to extend the sandbox writable paths "
            f"({CFG.ENV_PREFIX}_LLM_SANDBOX_WRITABLE_PATHS) / adjust the deny list "
            f"({CFG.ENV_PREFIX}_LLM_SANDBOX_DENY_READ_PATHS).",
            blocked=True,
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

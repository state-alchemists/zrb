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

Both return a blocked ``ToolReturn`` or ``None``; the default path is unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.capabilities.permission import (
    DENY,
    Capability,
    get_current_agent_mode,
    get_effective_policy,
)
from zrb.llm.capabilities.permission.policy import PATH_ARG_KEYS
from zrb.llm.capabilities.sandbox import (
    check_read,
    check_write,
    contains_denied_read_root,
    get_effective_sandbox_policy,
)
from zrb.llm.capabilities.sandbox.policy import SandboxPolicy
from zrb.llm.capabilities.tool_call.shell_call import is_sandbox_off
from zrb.llm.contracts.shared.agent_tool_result import tool_return

if TYPE_CHECKING:
    from pydantic_ai import RunContext, ToolReturn

# Every path-shaped argument spelling the sandbox judges, read-checked for all
# tools and write-checked for EDIT/UNKNOWN ones ("src" is write-checked because
# move_file deletes it; "dst" because it gets overwritten). The list is shared
# with the permission layer's `arg_pattern` matching (`PATH_ARG_KEYS`), so a
# spelling added for one layer covers both and they cannot drift.
#
# The snake_case spellings are what zrb's own tools declare; the camelCase and
# single-word ones are what an MCP server or a plugin declares, and a tool whose
# path argument is spelled `filePath` used to pass this gate with no check at
# all. An unlisted spelling is a fail-open, so the common ones are listed rather
# than discovered at run time.
#
# `cwd` is deliberately absent: it names the directory a call runs in, and a
# resume lists worktrees and selects one without writing a byte. The one tool
# that does write through a `cwd` — EnterWorktree — judges the repository root
# git resolves from it, on its create path only (`_repo_write_error`). A gate on
# `cwd` here refused a resume whose repository was read-only but whose worktree
# was not, which is a legitimate call.


def permission_gate(
    tool_name: str, capability: Capability, args: dict[str, object]
) -> "ToolReturn | None":
    """Return a blocked ``ToolReturn`` when policy denies the call."""
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
    tool_name: str,
    capability: Capability,
    args: dict[str, object],
    ctx: "RunContext[None] | None" = None,
) -> "ToolReturn | None":
    """Return a blocked ``ToolReturn`` when the sandbox denies a path."""
    # isinstance, not "is not None": anything that isn't a SandboxPolicy
    # (e.g. a MagicMock's auto-created `.deps`) falls back to the ambient read.
    deps = getattr(ctx, "deps", None)
    policy = deps if isinstance(deps, SandboxPolicy) else get_effective_sandbox_policy()
    if not policy.enabled:
        return None

    def _blocked(reason: str) -> "ToolReturn":
        return tool_return(
            f"Blocked by sandbox policy: {reason}. "
            "[SYSTEM SUGGESTION]: work within the project directory, or "
            "ask the user to extend the sandbox writable paths "
            f"({CFG.ENV_PREFIX}_LLM_SANDBOX_WRITABLE_PATHS) / adjust the deny list "
            f"({CFG.ENV_PREFIX}_LLM_SANDBOX_DENY_READ_PATHS).",
            blocked=True,
        )

    if not policy.allow_escape and is_sandbox_off(args):
        return _blocked(
            "dangerously_skip_sandbox was requested but escaping the sandbox "
            "is disabled in this deployment (LLM_SANDBOX_ALLOW_ESCAPE_ENABLED=false)"
        )

    cap_value = getattr(capability, "value", capability)
    if cap_value == Capability.EXECUTE.value:
        return None
    for key in PATH_ARG_KEYS:
        value = args.get(key)
        if isinstance(value, str):
            error = check_read(value, policy)
            if error is not None:
                return _blocked(error)
            # A directory can contain a deny-read root without being inside it.
            # A recursive reader (`Grep` via ripgrep, `AnalyzeCode`) would open
            # that root's files before the per-file check sees their results,
            # so the path is refused before the reader runs.
            contained_root = contains_denied_read_root(value, policy)
            if contained_root is not None:
                return _blocked(
                    f"'{value}' contains the protected directory "
                    f"'{contained_root}', which a recursive read would open "
                    "before any per-file check; pass a narrower path"
                )
    if cap_value in (Capability.EDIT.value, Capability.UNKNOWN.value):
        for key in PATH_ARG_KEYS:
            value = args.get(key)
            if isinstance(value, str):
                error = check_write(value, policy)
                if error is not None:
                    return _blocked(error)
    return None

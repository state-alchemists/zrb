"""Sandbox policy: what LLM-initiated tool calls may touch on the filesystem.

Consumed by both the in-process FS gate (``zrb.llm.agent.common``) and the
OS shell wrapper (``os_sandbox``). With ``enabled=False`` (the default) every
consumer is a no-op.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, replace

from zrb.attr.type import BoolAttr
from zrb.config.config import CFG
from zrb.config.mixins.llm_sandbox import DEFAULT_LLM_SANDBOX_DENY_READ_PATHS
from zrb.context.any_context import AnyContext
from zrb.util.attr import get_bool_attr

DEFAULT_DENY_READ_PATHS: tuple[str, ...] = DEFAULT_LLM_SANDBOX_DENY_READ_PATHS


@dataclass(frozen=True)
class SandboxPolicy:
    """Filesystem containment rules for LLM tool calls.

    ``writable_paths`` empty means automatic: the process working directory
    plus the system temp directory, resolved at check time (see
    ``resolved_writable_roots``).
    """

    enabled: bool = False
    writable_paths: tuple[str, ...] = ()
    deny_read_paths: tuple[str, ...] = DEFAULT_DENY_READ_PATHS
    os_shell: str = "auto"  # "auto" | "off"
    fallback: str = "warn"  # "warn" | "deny" when no OS mechanism exists
    allow_escape: bool = True  # honor dangerously_skip_sandbox


def resolve_sandbox_policy_from_config() -> SandboxPolicy:
    """Build the policy from ``CFG.LLM_SANDBOX_*``."""
    return SandboxPolicy(
        enabled=CFG.LLM_SANDBOX_ENABLED,
        writable_paths=tuple(CFG.LLM_SANDBOX_WRITABLE_PATHS),
        deny_read_paths=tuple(CFG.LLM_SANDBOX_DENY_READ_PATHS),
        os_shell=CFG.LLM_SANDBOX_OS_SHELL,
        fallback=CFG.LLM_SANDBOX_FALLBACK,
        allow_escape=CFG.LLM_SANDBOX_ALLOW_ESCAPE,
    )


# What the ``sandbox=`` task argument accepts; see ``coerce_sandbox``.
SandboxInput = SandboxPolicy | bool | None


def coerce_sandbox(
    ctx: AnyContext, raw: SandboxInput | BoolAttr
) -> SandboxPolicy | None:
    """Coerce a user-facing ``sandbox`` value into a policy.

    ``None`` → ``None`` (use ambient/CFG resolution), ``SandboxPolicy`` →
    itself, ``True``/``False`` → the config-derived policy with ``enabled``
    forced. Mirrors ``zrb.llm.permission.resolve_policy``.
    """
    if raw is None:
        return None
    if isinstance(raw, SandboxPolicy):
        return raw
    sandbox = get_bool_attr(ctx, raw)
    return replace(resolve_sandbox_policy_from_config(), enabled=sandbox)


def resolve_real(path: str) -> str:
    """Canonicalize a tool-supplied path: ``~`` → abs → realpath.

    ``realpath`` resolves the existing prefix and keeps the non-existent tail,
    which is what write checks need for not-yet-created targets
    (``write_file`` creates parent directories).
    """
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def resolved_writable_roots(policy: SandboxPolicy) -> tuple[str, ...]:
    """Realpath'd roots a tool call may write under.

    The automatic root is the process cwd, never a per-call ``cwd`` (that
    would let the model pick its own boundary, e.g. ``cwd="/"``). The temp
    dir is always included because the shell tool's PID-tracking wrapper
    writes a temp file from inside the sandbox; realpath covers Darwin's
    ``/tmp`` → ``/private/tmp`` symlink.
    """
    if policy.writable_paths:
        roots = [resolve_real(p) for p in policy.writable_paths]
    else:
        roots = [resolve_real(os.getcwd())]
    roots.append(resolve_real(tempfile.gettempdir()))
    if os.name == "posix":
        roots.append(resolve_real("/tmp"))
    return tuple(dict.fromkeys(roots))


def resolved_deny_read_roots(policy: SandboxPolicy) -> tuple[str, ...]:
    """Realpath'd deny-read roots, skipping entries absent on this machine."""
    roots = []
    for p in policy.deny_read_paths:
        rp = resolve_real(p)
        if os.path.exists(rp):
            roots.append(rp)
    return tuple(dict.fromkeys(roots))

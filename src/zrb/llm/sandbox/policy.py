"""Sandbox policy: what LLM-initiated tool calls may touch on the filesystem.

A ``SandboxPolicy`` is the single value both enforcement layers consume:

* the Python-level FS gate in ``zrb.llm.agent.common`` (in-process file tools),
* the OS-level shell wrapper in ``zrb.llm.sandbox.os_sandbox`` (subprocesses).

This package is a leaf (no ``zrb.llm.agent`` imports), mirroring
``zrb.llm.permission``. Default-off invariant: with ``enabled=False`` (the
default) every consumer reproduces today's behavior exactly.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, replace

from zrb.attr.type import BoolAttr
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
    # lazy: config is read per call so tests and downstream products (which
    # override CFG defaults at startup) always see current values.
    from zrb.config.config import CFG

    return SandboxPolicy(
        enabled=CFG.LLM_SANDBOX_ENABLED,
        writable_paths=tuple(CFG.LLM_SANDBOX_WRITABLE_PATHS),
        deny_read_paths=tuple(CFG.LLM_SANDBOX_DENY_READ_PATHS),
        os_shell=CFG.LLM_SANDBOX_OS_SHELL,
        fallback=CFG.LLM_SANDBOX_FALLBACK,
        allow_escape=CFG.LLM_SANDBOX_ALLOW_ESCAPE,
    )


# The shapes ``coerce_sandbox`` (and therefore the ``sandbox=`` task argument)
# accepts: an already-built policy, a bool (config-derived policy with
# ``enabled`` forced), or ``None`` (use ambient/CFG resolution).
SandboxInput = SandboxPolicy | bool | None


def coerce_sandbox(ctx: AnyContext, raw: SandboxInput | BoolAttr) -> SandboxPolicy | None:
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


def _realpath(path: str) -> str:
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def resolved_writable_roots(policy: SandboxPolicy, cwd: str = "") -> tuple[str, ...]:
    """Realpath'd roots a tool call may write under.

    Roots are realpath'd because both enforcement layers compare against real
    paths (Seatbelt matches real paths; the FS gate realpaths the target).

    The system temp dir is always writable — even with explicit
    ``writable_paths`` — because the shell tool's PID-tracking wrapper writes
    a temp file from *inside* the sandbox, and temp dirs are world-writable by
    design anyway. On POSIX ``/tmp`` is added via realpath, which also covers
    Darwin's symlinks (``/tmp`` → ``/private/tmp``, ``$TMPDIR`` →
    ``/private/var/folders/...``).
    """
    if policy.writable_paths:
        roots = [_realpath(p) for p in policy.writable_paths]
    else:
        roots = [_realpath(cwd or os.getcwd())]
    roots.append(_realpath(tempfile.gettempdir()))
    if os.name == "posix":
        roots.append(_realpath("/tmp"))
    return tuple(dict.fromkeys(roots))


def resolved_deny_read_roots(policy: SandboxPolicy) -> tuple[str, ...]:
    """Realpath'd deny-read roots, dropping entries absent on this machine.

    Non-existent entries are skipped: they can't be read anyway, and dropping
    them keeps generated OS profiles (SBPL/bwrap args) clean.
    """
    roots = []
    for p in policy.deny_read_paths:
        rp = _realpath(p)
        if os.path.exists(rp):
            roots.append(rp)
    return tuple(dict.fromkeys(roots))

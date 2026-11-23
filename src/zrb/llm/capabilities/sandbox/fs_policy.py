"""Python-level filesystem checks for in-process file tools.

Targets are realpath'd (catching symlink escapes); the check/``open()``
TOCTOU race is accepted, since the agent process itself cannot be jailed
without losing its network loop.
"""

from __future__ import annotations

import os

from zrb.llm.capabilities.sandbox.policy import (
    SandboxPolicy,
    resolve_real,
    resolved_deny_read_roots,
    resolved_writable_roots,
)


def is_within(child: str, root: str) -> bool:
    child_n = os.path.normcase(child)
    root_n = os.path.normcase(root)
    try:
        return os.path.commonpath([child_n, root_n]) == root_n
    except ValueError:
        # Different drives (Windows) or mixed abs/rel — not within.
        return False


def check_read(path: str, policy: SandboxPolicy) -> str | None:
    """Return an error message if reading ``path`` is blocked, else ``None``."""
    real = resolve_real(path)
    for root in resolved_deny_read_roots(policy):
        if is_within(real, root):
            return (
                f"'{path}' resolves into the protected directory '{root}' "
                "which holds credentials and may not be read"
            )
    return None


def is_read_allowed(path: str, policy: SandboxPolicy) -> bool:
    """Whether reading ``path`` is permitted, for a reader that opens many files.

    The gate judges the argument a call was given; a recursive reader then opens
    every file underneath it, which can be a parent of a deny-read root or a
    workspace directory holding a symlink into one. Callers ask this per file
    instead of per call. A disabled policy allows everything, so the no-sandbox
    path stays exactly as it was.
    """
    if not policy.enabled:
        return True
    return check_read(path, policy) is None


def contains_denied_read_root(path: str, policy: SandboxPolicy) -> str | None:
    """The deny-read root ``path`` contains, or ``None``.

    A recursive reader opens every file beneath the path it is given, and
    ``Grep``'s ripgrep subprocess matches file contents before the per-file
    filter can drop a result. A path that contains a deny-read root therefore
    has to be refused up front, not filtered afterwards. Returns the root so the
    gate can name it; a disabled policy contains nothing, matching
    ``is_read_allowed``.
    """
    if not policy.enabled:
        return None
    real = resolve_real(path)
    for root in resolved_deny_read_roots(policy):
        if is_within(root, real):
            return root
    return None


def check_write(path: str, policy: SandboxPolicy) -> str | None:
    """Return an error message if writing ``path`` is blocked, else ``None``.

    A path inside a deny-read root is also unwritable (a secret you cannot
    read you also cannot overwrite or plant — e.g. ``~/.ssh/authorized_keys``).
    """
    real = resolve_real(path)
    for root in resolved_deny_read_roots(policy):
        if is_within(real, root):
            return (
                f"'{path}' resolves into the protected directory '{root}' "
                "and may not be written"
            )
    roots = resolved_writable_roots(policy)
    if not any(is_within(real, root) for root in roots):
        readable_roots = ", ".join(f"'{r}'" for r in roots)
        return f"'{path}' is outside the sandbox writable roots ({readable_roots})"
    return None

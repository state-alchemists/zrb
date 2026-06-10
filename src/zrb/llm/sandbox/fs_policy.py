"""Python-level filesystem checks for in-process file tools.

These checks back the ``_sandbox_gate`` in ``zrb.llm.agent.common``. They are
advisory-at-the-Python-layer by design: the target is realpath'd at check time
(so symlink escapes are caught), but a race between check and ``open()``
(TOCTOU) is accepted — kernel-enforced containment is the OS shell layer's
job, while these tools run inside the agent process which cannot be jailed
without losing the LLM network loop.

Windows notes: comparisons are ``normcase``'d (case-insensitive filesystems),
and cross-drive comparisons (``C:`` vs ``D:``) raise ``ValueError`` inside
``commonpath`` — treated as "outside the root", i.e. blocked for writes.
"""

from __future__ import annotations

import os

from zrb.llm.sandbox.policy import (
    SandboxPolicy,
    resolved_deny_read_roots,
    resolved_writable_roots,
)


def resolve_real(path: str) -> str:
    """Canonicalize a tool-supplied path: ``~`` → abs → realpath.

    ``realpath`` resolves the existing prefix and keeps the non-existent tail,
    which is exactly what write checks need for not-yet-created targets
    (``write_file`` creates parent directories).
    """
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def _is_within(child: str, root: str) -> bool:
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
        if _is_within(real, root):
            return (
                f"'{path}' resolves into the protected directory '{root}' "
                "which holds credentials and may not be read"
            )
    return None


def check_write(path: str, policy: SandboxPolicy, cwd: str = "") -> str | None:
    """Return an error message if writing ``path`` is blocked, else ``None``.

    A path inside a deny-read root is also unwritable (a secret you cannot
    read you also cannot overwrite or plant — e.g. ``~/.ssh/authorized_keys``).
    ``cwd`` only seeds the *automatic* writable roots when the policy doesn't
    pin ``writable_paths``; a per-call ``cwd`` tool argument must NOT be passed
    here (the model could escape by passing ``cwd="/"``).
    """
    real = resolve_real(path)
    for root in resolved_deny_read_roots(policy):
        if _is_within(real, root):
            return (
                f"'{path}' resolves into the protected directory '{root}' "
                "and may not be written"
            )
    roots = resolved_writable_roots(policy, cwd)
    if not any(_is_within(real, root) for root in roots):
        readable_roots = ", ".join(f"'{r}'" for r in roots)
        return f"'{path}' is outside the sandbox writable roots " f"({readable_roots})"
    return None

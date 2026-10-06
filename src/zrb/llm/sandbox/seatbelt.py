"""macOS Seatbelt (SBPL) profile generation for sandboxed shell commands.

``sandbox-exec`` is deprecated but functional, and execs the target in place,
so the spawned PID is still the shell's.

SBPL is last-match-wins, so rules go broad → specific: allow all, deny writes,
re-allow writable roots, deny reads of credential dirs.

A sandboxed process cannot exec set[ug]id binaries (``/bin/ps``, ``sudo``);
the shell tool's PID tracking falls back to ``pgrep``.
"""

from __future__ import annotations

from zrb.llm.sandbox.policy import (
    SandboxPolicy,
    resolved_deny_read_roots,
    resolved_writable_roots,
)

# Device nodes a non-interactive shell command legitimately writes to.
_WRITABLE_DEV_LITERALS = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty")


def sbpl_quote(path: str) -> str:
    """Quote a path as an SBPL string literal.

    Raises ``ValueError`` for paths SBPL cannot represent safely; the caller
    applies the policy's fallback mode instead of emitting a broken profile.
    """
    if "\n" in path or "\r" in path or "\x00" in path:
        raise ValueError(f"path not representable in a sandbox profile: {path!r}")
    escaped = path.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_sbpl(policy: SandboxPolicy) -> str:
    """Generate the SBPL profile implementing the sandbox policy."""
    writable = resolved_writable_roots(policy)
    deny_read = resolved_deny_read_roots(policy)

    lines = [
        "(version 1)",
        "(allow default)",
        "(deny file-write*)",
        "(allow file-write*",
    ]
    for root in writable:
        lines.append(f"  (subpath {sbpl_quote(root)})")
    for dev in _WRITABLE_DEV_LITERALS:
        lines.append(f"  (literal {sbpl_quote(dev)})")
    lines.append('  (subpath "/dev/fd"))')
    if deny_read:
        lines.append("(deny file-read* file-read-metadata")
        for root in deny_read:
            lines.append(f"  (subpath {sbpl_quote(root)})")
        lines[-1] += ")"
    return "\n".join(lines)

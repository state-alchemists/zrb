"""macOS Seatbelt (SBPL) profile generation for sandboxed shell commands.

``sandbox-exec -p <profile>`` is deprecated-but-functional — Chrome, Bazel and
OpenAI Codex all still ship on it, and Apple keeps the underlying
``sandbox_init`` API working. ``sandbox-exec`` **execs** the target after
initializing the sandbox, so the spawned PID is still the shell: process-group
handling, timeout kill, and PID tracking in the shell tool are unaffected.

SBPL evaluation is last-match-wins, so rules are ordered broad → specific:
allow everything (network/exec/read stay open in v1), deny all writes, re-allow
writes under the policy's writable roots, then deny reads of credential dirs.

Known limitation: a sandboxed process cannot exec set[ug]id binaries — the
kernel refuses regardless of the profile. On macOS that includes ``/bin/ps``
(setuid root) and ``sudo``. ``pgrep``/``pkill`` are not setuid and keep
working; the shell tool's PID-tracking wrapper falls back accordingly.
"""

from __future__ import annotations

from zrb.llm.sandbox.policy import (
    SandboxPolicy,
    resolved_deny_read_roots,
    resolved_writable_roots,
)

# Device nodes a non-interactive shell command legitimately writes to.
_WRITABLE_DEV_LITERALS = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty")


def _sbpl_quote(path: str) -> str:
    """Quote a path as an SBPL string literal.

    Raises ``ValueError`` for paths SBPL cannot represent safely; the caller
    applies the policy's fallback mode instead of emitting a broken profile.
    """
    if "\n" in path or "\r" in path or "\x00" in path:
        raise ValueError(f"path not representable in a sandbox profile: {path!r}")
    escaped = path.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_sbpl(policy: SandboxPolicy, cwd: str = "") -> str:
    """Generate the SBPL profile implementing the sandbox policy."""
    writable = resolved_writable_roots(policy, cwd)
    deny_read = resolved_deny_read_roots(policy)

    lines = [
        "(version 1)",
        "(allow default)",
        "(deny file-write*)",
        "(allow file-write*",
    ]
    for root in writable:
        lines.append(f"  (subpath {_sbpl_quote(root)})")
    for dev in _WRITABLE_DEV_LITERALS:
        lines.append(f"  (literal {_sbpl_quote(dev)})")
    lines.append('  (subpath "/dev/fd"))')
    if deny_read:
        lines.append("(deny file-read* file-read-metadata")
        for root in deny_read:
            lines.append(f"  (subpath {_sbpl_quote(root)})")
        lines[-1] += ")"
    return "\n".join(lines)

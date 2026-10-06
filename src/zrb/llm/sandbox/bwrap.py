"""Linux bubblewrap argument generation for sandboxed shell commands.

No ``--unshare-net`` (network stays open) and no ``--unshare-pid``, so the
target keeps the PID / process-group semantics the shell tool's timeout-kill
relies on.

Later binds override earlier ones, so deny-read masks go last and stay masked
even inside a writable root.
"""

from __future__ import annotations

import os

from zrb.llm.sandbox.policy import (
    SandboxPolicy,
    resolved_deny_read_roots,
    resolved_writable_roots,
)


def build_bwrap_argv(bwrap_path: str, policy: SandboxPolicy) -> list[str]:
    """Build the bwrap argv prefix (ends with ``--``; append the shell argv)."""
    argv = [
        bwrap_path,
        "--die-with-parent",
        "--ro-bind",
        "/",
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        "--proc",
        "/proc",
    ]
    for root in resolved_writable_roots(policy):
        argv += ["--bind", root, root]
    for path in resolved_deny_read_roots(policy):
        if os.path.isdir(path):
            argv += ["--tmpfs", path]
        else:
            argv += ["--ro-bind", "/dev/null", path]
    argv.append("--")
    return argv

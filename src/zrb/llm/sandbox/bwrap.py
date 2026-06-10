"""Linux bubblewrap argument generation for sandboxed shell commands.

bwrap is a single static binary, ubiquitous as flatpak's runtime dependency.
Deliberately **no** ``--unshare-net`` (network stays open in v1) and **no**
``--unshare-pid``: without a PID namespace bwrap execs the target in place,
preserving the PID / process-group semantics the shell tool's timeout-kill and
background-PID tracking rely on.

Mount order matters (later binds override earlier ones): read-only root first,
then dev/proc, then the writable binds, then the deny-read masks last — so a
credential directory stays masked even when it sits inside a writable root.
"""

from __future__ import annotations

import os

from zrb.llm.sandbox.policy import (
    SandboxPolicy,
    resolved_deny_read_roots,
    resolved_writable_roots,
)


def build_bwrap_argv(
    bwrap_path: str, policy: SandboxPolicy, cwd: str = ""
) -> list[str]:
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
    for root in resolved_writable_roots(policy, cwd):
        argv += ["--bind", root, root]
    for path in resolved_deny_read_roots(policy):
        if os.path.isdir(path):
            argv += ["--tmpfs", path]
        else:
            argv += ["--ro-bind", "/dev/null", path]
    argv.append("--")
    return argv

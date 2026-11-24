"""Linux bubblewrap argument generation for sandboxed shell commands.

The sandbox gets its own PID namespace (``--unshare-pid``), so the procfs
mounted at ``/proc`` lists only the sandbox's own processes. Sharing the
host's PID namespace would let ``/proc/<pid>/root`` and ``/proc/<pid>/cwd``
resolve into another same-uid process's mount namespace, reopening the paths
the read-only root and deny-read masks close.

No ``--unshare-net``: network stays open. Process-group semantics survive a
PID namespace, because it does not change process groups: bwrap and the
command stay in the group the parent created with ``start_new_session``, so
the parent still kills that group and the bwrap child by host PID through
``killpg`` and psutil.

Later binds override earlier ones, so deny-read masks go last and stay masked
even inside a writable root.
"""

from __future__ import annotations

import os

from zrb.llm.capabilities.sandbox.policy import (
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
        # Own PID namespace, then a procfs for it: a procfs mounted while
        # sharing the host PID namespace lists host processes, and
        # `/proc/<pid>/root` re-enters their mount namespaces.
        "--unshare-pid",
        "--proc",
        "/proc",
    ]
    for root in resolved_writable_roots(policy):
        # `--bind` refuses a source that is not there (`--bind-try` is the
        # tolerant form), and the automatic set names LLM_WORKTREE_DIR, which
        # the first worktree creates during a tool call — long after the first
        # sandboxed command. Skipping it here costs nothing: a path that does
        # not exist has nothing inside it to write, and the bind is there for
        # every call made after the parent process creates it.
        if not os.path.exists(root):
            continue
        argv += ["--bind", root, root]
    for path in resolved_deny_read_roots(policy):
        if os.path.isdir(path):
            argv += ["--tmpfs", path]
        else:
            argv += ["--ro-bind", "/dev/null", path]
    argv.append("--")
    return argv

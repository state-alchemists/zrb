"""Sandbox: filesystem containment for LLM-initiated tool calls.

Two enforcement layers behind one ``SandboxPolicy`` (opt-in, off by default):

* ``fs_policy`` — Python-level path checks applied by the ``_sandbox_gate``
  in ``zrb.llm.agent.common`` to in-process file tools (Write/Edit/RM/MV and
  reads of credential directories).
* ``os_sandbox`` — kernel-enforced wrapping of shell subprocesses (Seatbelt
  on macOS, bubblewrap on Linux; Windows has no mechanism and follows the
  policy's ``fallback`` mode).

The approval layer (``zrb.llm.permission``) controls *intent* — what the user
agrees to. The sandbox controls *blast radius* — what an approved call can
actually touch. This package is a leaf (no ``zrb.llm.agent`` imports).
"""

from __future__ import annotations

from zrb.llm.sandbox.fs_policy import check_read, check_write, resolve_real
from zrb.llm.sandbox.os_sandbox import (
    ESCAPE_NOTE,
    SandboxUnavailableError,
    build_sandboxed_argv,
)
from zrb.llm.sandbox.policy import (
    DEFAULT_DENY_READ_PATHS,
    SandboxInput,
    SandboxPolicy,
    coerce_sandbox,
    resolve_sandbox_policy_from_config,
    resolved_deny_read_roots,
    resolved_writable_roots,
)
from zrb.llm.sandbox.state import (
    current_sandbox_policy,
    get_current_sandbox_policy,
    get_effective_sandbox_policy,
    set_current_sandbox_policy,
)

__all__ = [
    "DEFAULT_DENY_READ_PATHS",
    "SandboxInput",
    "SandboxPolicy",
    "coerce_sandbox",
    "resolve_sandbox_policy_from_config",
    "resolved_deny_read_roots",
    "resolved_writable_roots",
    "check_read",
    "check_write",
    "resolve_real",
    "ESCAPE_NOTE",
    "SandboxUnavailableError",
    "build_sandboxed_argv",
    "current_sandbox_policy",
    "get_current_sandbox_policy",
    "set_current_sandbox_policy",
    "get_effective_sandbox_policy",
]

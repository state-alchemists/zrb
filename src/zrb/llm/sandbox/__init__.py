"""Sandbox: opt-in filesystem containment for LLM-initiated tool calls.

``fs_policy`` checks paths for in-process file tools; ``os_sandbox`` wraps
shell subprocesses (Seatbelt on macOS, bubblewrap on Linux). Leaf package:
no ``zrb.llm.agent`` imports.
"""

from __future__ import annotations

from zrb.llm.sandbox.fs_policy import check_read, check_write
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
    resolve_real,
    resolve_sandbox_policy_from_config,
    resolved_deny_read_roots,
    resolved_writable_roots,
)
from zrb.llm.sandbox.state import (
    current_sandbox_policy,
    get_current_sandbox_policy,
    get_effective_sandbox_policy,
    sandbox_policy,
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
    "sandbox_policy",
    "get_effective_sandbox_policy",
]

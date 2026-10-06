"""OS-level sandbox dispatch for subprocesses.

macOS uses ``sandbox-exec`` (``seatbelt``), Linux uses ``bwrap`` when
installed. Elsewhere the policy's ``fallback`` decides: ``"warn"`` runs
unsandboxed with a visible warning, ``"deny"`` raises
:class:`SandboxUnavailableError`.
"""

from __future__ import annotations

import platform
import shutil

from zrb.config.config import CFG
from zrb.llm.permission.observability import record_policy_decision
from zrb.llm.sandbox.bwrap import build_bwrap_argv
from zrb.llm.sandbox.policy import SandboxPolicy
from zrb.llm.sandbox.seatbelt import build_sbpl

ESCAPE_NOTE = "[NOTE] executed outside the sandbox (dangerously_skip_sandbox=true)"


class SandboxUnavailableError(Exception):
    """No OS sandbox mechanism is available and the policy demands one."""


def format_sandbox_denied_message(e: SandboxUnavailableError) -> str:
    """Model-facing refusal text for a `fallback="deny"` sandbox error."""
    return (
        f"Command refused by sandbox policy: {e}. "
        "[SYSTEM SUGGESTION]: this deployment requires OS-level sandboxing "
        f"for shell commands ({CFG.ENV_PREFIX}_LLM_SANDBOX_FALLBACK=deny)."
    )


def build_sandboxed_argv(
    argv: list[str],
    policy: SandboxPolicy,
    skip: bool = False,
) -> tuple[list[str], str | None]:
    """Prefix ``argv`` with the platform sandbox per ``policy``.

    Returns ``(argv, note)`` for ``create_subprocess_exec``; ``note`` is an
    optional escape notice or fallback warning to prepend to tool output.

    Raises :class:`SandboxUnavailableError` when no mechanism exists and
    ``policy.fallback == "deny"``, or when an escape is requested while
    ``policy.allow_escape`` is off.
    """
    plain = list(argv)
    if not policy.enabled or policy.os_shell == "off":
        record_policy_decision(layer="sandbox", decision="disabled")
        return plain, None
    if skip:
        if not policy.allow_escape:
            # The sandbox gate blocks this earlier; defense-in-depth here.
            record_policy_decision(
                layer="sandbox", decision="deny", reason="escape_disabled"
            )
            raise SandboxUnavailableError(
                "dangerously_skip_sandbox requested but escaping the sandbox "
                "is disabled (LLM_SANDBOX_ALLOW_ESCAPE=false)"
            )
        record_policy_decision(layer="sandbox", decision="escape")
        return plain, ESCAPE_NOTE

    system = platform.system()
    if system == "Darwin":
        sandbox_exec = shutil.which("sandbox-exec")
        if not sandbox_exec:
            return _fallback(plain, policy, "sandbox-exec not found")
        try:
            profile = build_sbpl(policy)
        except ValueError as e:
            return _fallback(plain, policy, f"cannot generate sandbox profile: {e}")
        return [sandbox_exec, "-p", profile, *plain], None
    if system == "Linux":
        bwrap = shutil.which("bwrap")
        if not bwrap:
            return _fallback(plain, policy, "bwrap (bubblewrap) is not installed")
        return [*build_bwrap_argv(bwrap, policy), *plain], None
    return _fallback(plain, policy, f"no OS sandbox mechanism exists on {system}")


def _fallback(
    plain: list[str], policy: SandboxPolicy, reason: str
) -> tuple[list[str], str | None]:
    if policy.fallback == "deny":
        record_policy_decision(
            layer="sandbox", decision="deny", reason=reason, fallback="deny"
        )
        raise SandboxUnavailableError(reason)
    record_policy_decision(
        layer="sandbox", decision="fallback", reason=reason, fallback="warn"
    )
    return plain, (
        f"[WARNING] sandbox unavailable ({reason}); "
        "the command ran WITHOUT OS-level isolation"
    )

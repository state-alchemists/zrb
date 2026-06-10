"""OS-level sandbox dispatch for shell subprocesses.

``build_sandboxed_argv`` is the single entry point the shell tools call right
before spawning. It returns discrete argv elements for
``asyncio.create_subprocess_exec`` — no shell quoting is ever involved.

Platform matrix:

* macOS  → ``sandbox-exec -p <SBPL>`` (see ``seatbelt``)
* Linux  → ``bwrap`` when installed (see ``bwrap``)
* Windows / Linux-without-bwrap → no OS mechanism; the policy's ``fallback``
  mode decides: ``"warn"`` runs the command unsandboxed with a visible warning,
  ``"deny"`` raises :class:`SandboxUnavailableError`. Never a silent
  passthrough.
"""

from __future__ import annotations

import platform
import shutil

from zrb.llm.sandbox.bwrap import build_bwrap_argv
from zrb.llm.sandbox.policy import SandboxPolicy
from zrb.llm.sandbox.seatbelt import build_sbpl

ESCAPE_NOTE = "[NOTE] executed outside the sandbox (dangerously_skip_sandbox=true)"


class SandboxUnavailableError(Exception):
    """No OS sandbox mechanism is available and the policy demands one."""


def build_sandboxed_argv(
    shell: str,
    shell_flag: str,
    command: str,
    cwd: str,
    policy: SandboxPolicy,
    skip: bool = False,
) -> tuple[list[str], str | None]:
    """Wrap a shell invocation in the platform sandbox per ``policy``.

    Returns ``(argv, note)``: ``argv`` to pass to ``create_subprocess_exec``
    and an optional human/model-facing note (escape notice or fallback
    warning) the caller prepends to the tool output.

    Raises :class:`SandboxUnavailableError` when no mechanism exists and
    ``policy.fallback == "deny"``, or when an escape is requested while
    ``policy.allow_escape`` is off.
    """
    plain = [shell, shell_flag, command]
    if not policy.enabled or policy.os_shell == "off":
        return plain, None
    if skip:
        if not policy.allow_escape:
            # The sandbox gate blocks this earlier; defense-in-depth here.
            raise SandboxUnavailableError(
                "dangerously_skip_sandbox requested but escaping the sandbox "
                "is disabled (LLM_SANDBOX_ALLOW_ESCAPE=false)"
            )
        return plain, ESCAPE_NOTE

    system = platform.system()
    if system == "Darwin":
        sandbox_exec = shutil.which("sandbox-exec")
        if not sandbox_exec:
            return _fallback(plain, policy, "sandbox-exec not found")
        try:
            profile = build_sbpl(policy, cwd)
        except ValueError as e:
            return _fallback(plain, policy, f"cannot generate sandbox profile: {e}")
        return [sandbox_exec, "-p", profile, *plain], None
    if system == "Linux":
        bwrap = shutil.which("bwrap")
        if not bwrap:
            return _fallback(plain, policy, "bwrap (bubblewrap) is not installed")
        return [*build_bwrap_argv(bwrap, policy, cwd), *plain], None
    return _fallback(plain, policy, f"no OS sandbox mechanism exists on {system}")


def _fallback(
    plain: list[str], policy: SandboxPolicy, reason: str
) -> tuple[list[str], str | None]:
    if policy.fallback == "deny":
        raise SandboxUnavailableError(reason)
    return plain, (
        f"[WARNING] sandbox unavailable ({reason}); "
        "the command ran WITHOUT OS-level isolation"
    )

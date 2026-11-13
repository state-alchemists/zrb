"""One small-model opinion on whether a shell command is safe to skip (ADR-0141).

This is the *last* thing consulted before a person is asked. It sits below
every rule — a permission `ask`, a `PreToolUse` hook's `permissionDecision:
"ask"`, an allow-list — because those are decisions someone wrote down and a
model's opinion is not. What it can do is narrow what a person is asked:

* with ``LLM_SHELL_JUDGE_AUTO_APPROVE_ENABLED`` on, a `safe` verdict approves
  the call without a prompt;
* otherwise it only adds one line to the prompt, so the person sees what it
  saw — which is the half that cannot widen anything.

It is deliberately **reasoning-blind**. The judge reads the command, the
directory it runs in, whether the sandbox is off, and how much uncommitted
work the repository holds. It does not read the conversation, the assistant's
own text, or earlier tool results: Anthropic reports that including them
*lowered* classifier accuracy, and the reason is obvious once stated — the
model being judged would be writing part of its own input, and "the user
already approved something like this" is exactly the argument a command needs
to survive.

It is also not a security boundary. Anthropic's own classifier misses ~17% of
real overeager actions, and every harness that ships one says so in its docs.
The boundary is the sandbox; this is a prompt filter that fails closed.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.shared.agent_runner import create_agent
from zrb.llm.tool_call.judge_note import (
    JUDGE_CAUTION,
    JUDGE_DANGEROUS,
    JUDGE_SAFE,
    JUDGE_UNKNOWN,
    MAX_JUDGE_REASON_CHARS,
)
from zrb.util.truncate import truncate_display

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from zrb.llm.agent.types import ToolCallPart

# A judge that has not answered by now is not going to answer usefully. The
# prompt has waited behind it, so the bound is the person's patience, not the
# model's.
JUDGE_TIMEOUT_SECONDS = 20.0

# Past this a command is not read as a command. Claude Code prompts
# unconditionally at the same length; so does this, and for less money.
_MAX_COMMAND_CHARS = 10_000

# `git status` is read to give the judge the one fact the command cannot carry:
# whether a destructive git operation has anything to destroy.
_GIT_STATUS_TIMEOUT_SECONDS = 2.0

# What the model is asked to answer: one of three words, then a colon.
_VERDICT_LINE = re.compile(
    r"^\s*(safe|caution|dangerous)\s*[:\-—–]\s*(.*)$", re.IGNORECASE
)

# Anything outside this set is not a shell command in the sense this judges:
# `Shell` carries a `command` string; `RunZrbTask` carries a task name, and
# judging a task name against a shell-command rubric reads noise as risk.
_SHELL_ARG = "command"


@dataclass(frozen=True)
class ShellVerdict:
    """What the judge decided, and the one sentence it says why."""

    level: str
    reason: str

    @property
    def is_safe(self) -> bool:
        return self.level == JUDGE_SAFE


def is_judgeable_shell_call(call: "ToolCallPart") -> bool:
    """Whether *call* is a shell command with text worth judging."""
    # lazy: heavy third-party
    from zrb.llm.permission import Capability
    from zrb.llm.permission.capability import tool_capability
    from zrb.llm.util.tool_args import parse_tool_args

    args = parse_tool_args(call)
    if not isinstance(args, dict):
        return False
    command = args.get(_SHELL_ARG)
    if not isinstance(command, str) or not command.strip():
        return False
    return tool_capability(call) == Capability.EXECUTE


def parse_verdict(output: str) -> ShellVerdict:
    """Read the model's answer; anything unreadable is `unknown`, never safe.

    Fail-closed is the whole contract: a malformed answer, an empty one, or a
    word outside the three allowed is a judge that did not decide, and a
    command nobody decided about is a command somebody has to be asked about.
    """
    for line in str(output or "").splitlines():
        match = _VERDICT_LINE.match(line)
        if match is None:
            continue
        level = match.group(1).lower()
        reason = " ".join(match.group(2).split())
        reason = truncate_display(reason, MAX_JUDGE_REASON_CHARS)
        return ShellVerdict(level=level, reason=reason)
    return ShellVerdict(
        level=JUDGE_UNKNOWN,
        reason="the judge answered in no shape that names a verdict",
    )


class ShellJudgeError(Exception):
    """The judge did not produce a verdict: a model error, a timeout, no agent."""


async def judge_shell_command(
    command: str,
    *,
    cwd: str = "",
    sandbox_off: bool = False,
    model: "str | Model | None" = None,
) -> ShellVerdict:
    """Judge one command. Raises `ShellJudgeError` when the judge did not decide.

    The raising half is separated from `judge_or_unknown` so the broad catch
    that has to exist here can re-raise instead of swallowing: a handler that
    only logs is what the broad-except ratchet counts, and rightly, since a
    swallowed error and a considered "unknown" look identical from outside.
    """
    text = command.strip()
    if len(text) > _MAX_COMMAND_CHARS:
        return ShellVerdict(
            level=JUDGE_UNKNOWN,
            reason=f"too long to judge ({len(text)} characters)",
        )
    try:
        agent = create_agent(
            model=resolve_configured_small_model(model),
            system_prompt=get_prompt("shell_judge"),
            resolve_model=False,
        )
        payload = await asyncio.to_thread(
            _build_payload, text, cwd, sandbox_off
        )
        result = await asyncio.wait_for(
            agent.run(payload), timeout=JUDGE_TIMEOUT_SECONDS
        )
    except Exception as error:
        CFG.LOGGER.debug(f"Shell judge failed: {error}")
        raise ShellJudgeError(str(error) or type(error).__name__) from error
    _log_spend(result)
    return parse_verdict(str(getattr(result, "output", "") or ""))


async def judge_or_unknown(
    command: str,
    *,
    cwd: str = "",
    sandbox_off: bool = False,
    model: "str | Model | None" = None,
) -> ShellVerdict:
    """`judge_shell_command`, with every failure turned into a verdict.

    This is what an approval calls: an exception here would abort an approval
    that is otherwise fine, so the contract is a verdict, always — the
    pessimistic one when anything went wrong.
    """
    try:
        return await judge_shell_command(
            command, cwd=cwd, sandbox_off=sandbox_off, model=model
        )
    except ShellJudgeError:
        return ShellVerdict(level=JUDGE_UNKNOWN, reason="the judge did not finish")


def _build_payload(command: str, cwd: str, sandbox_off: bool) -> str:
    """The judge's whole input: the command, and the facts it cannot carry."""
    directory = cwd or os.getcwd()
    dirt = uncommitted_files(directory)
    sandbox = (
        "off — the command can write and reach the network anywhere"
        if sandbox_off
        else "on — writes are bounded to the workspace"
    )
    return (
        f"Command:\n{command}\n\n"
        f"Working directory: {directory}\n"
        f"Sandbox: {sandbox}\n"
        f"Uncommitted files in this repository: {dirt}"
    )


def uncommitted_files(directory: str) -> str:
    """How many paths `git status` reports, or why that could not be read."""
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=_GIT_STATUS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown (not a readable repository)"
    if completed.returncode != 0:
        return "unknown (not a git repository)"
    counted = len([line for line in completed.stdout.splitlines() if line.strip()])
    return str(counted)


def _log_spend(result: object) -> None:
    """Say what the call cost, for the developer reading the log.

    The judge's tokens are not in `/usage` yet: only the turn runner writes
    usage records, and this call sits beside it rather than under it. M0 —
    component attribution — is what makes it visible, which is why it is being
    built after this feature rather than before it.
    """
    usage = getattr(result, "usage", None)
    if usage is None:
        return
    CFG.LOGGER.debug(
        "Shell judge usage: "
        f"in={getattr(usage, 'input_tokens', 0)} "
        f"out={getattr(usage, 'output_tokens', 0)} "
        f"cache_read={getattr(usage, 'cache_read_tokens', 0)}"
    )


__all__ = [
    "ShellVerdict",
    "ShellJudgeError",
    "JUDGE_TIMEOUT_SECONDS",
    "is_judgeable_shell_call",
    "judge_or_unknown",
    "judge_shell_command",
    "parse_verdict",
    "uncommitted_files",
    "JUDGE_CAUTION",
    "JUDGE_DANGEROUS",
    "JUDGE_SAFE",
    "JUDGE_UNKNOWN",
]

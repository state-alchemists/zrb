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
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.shared.prompt_text import get_prompt
from zrb.llm.shared.agent_runner import create_agent
from zrb.llm.shared.usage_log import COMPONENT_SHELL_JUDGE, record_agent_usage
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

# The shell tool's runtime name and command argument live in
# `tool_call/shell_call.py`: the approval formatter, the read-only policy and
# this judge all have to recognise the same call, and one of them owning the
# shape is what keeps them from recognising it three slightly different ways.


@dataclass(frozen=True)
class ShellVerdict:
    """What the judge decided, the one sentence it says why, and the risk facts
    it was shown."""

    level: str
    reason: str
    facts: str = ""

    @property
    def is_safe(self) -> bool:
        """A `safe` verdict *that says why*. A bare word is not enough to skip
        a prompt: a truncated or malformed answer can name a level with nothing
        behind it, and that is a judge that did not decide."""
        return self.level == JUDGE_SAFE and bool(self.reason.strip())


class JudgeVerdict(BaseModel):
    """The judge's answer, shaped by the model call rather than read out of prose.

    Requiring the shape is the point. The answer used to be one line of text a
    regex went looking for, so a model that ignored the format still looked like
    a verdict until the parse said otherwise; now the model answers through a
    schema, and an answer that does not fit it is a failed call — which is
    `unknown`, which asks.
    """

    level: Literal["safe", "caution", "dangerous"]
    """Three words and no fourth: a judge that cannot decide answers nothing at
    all, rather than a fourth word this side has to interpret."""

    reason: str = ""
    """What it saw, in one sentence. An empty reason is not safe — see
    `ShellVerdict.is_safe`: the sentence is half the verdict, not decoration."""


def parse_verdict(output: str) -> ShellVerdict:
    """Read a text answer; anything unreadable is `unknown`, never safe.

    The fallback, for a model that answers with prose anyway. The judge asks for
    `JudgeVerdict` and normally gets one; this is what keeps a model which
    ignores the schema — a provider without tool calling, say — from being read
    as having decided.

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
        if not reason:
            # `SAFE:` with nothing after it is a truncation or a model that
            # ignored the format, not a judgement — and the one word must not
            # be enough to skip a prompt.
            return ShellVerdict(
                level=JUDGE_UNKNOWN,
                reason="the judge named a verdict without saying why",
            )
        reason = truncate_display(reason, MAX_JUDGE_REASON_CHARS)
        return ShellVerdict(level=level, reason=reason)
    return ShellVerdict(
        level=JUDGE_UNKNOWN,
        reason="the judge answered in no shape that names a verdict",
    )


class ShellJudgeError(Exception):
    """The judge did not produce a verdict: a model error, a timeout, no agent."""


def verdict_from_output(output: object) -> ShellVerdict:
    """The model's answer as a `ShellVerdict`; anything unreadable is `unknown`.

    A typed answer and a text one take the same road once they arrive: the level
    must be one of the three, and a level with no reason behind it is a judge
    that named something and did not decide. `is_safe` depends on the second
    rule, so it is enforced here rather than trusted from the model.
    """
    if not isinstance(output, JudgeVerdict):
        return parse_verdict(str(output or ""))
    reason = " ".join(str(output.reason).split())
    if not reason:
        return ShellVerdict(
            level=JUDGE_UNKNOWN,
            reason="the judge named a verdict without saying why",
        )
    return ShellVerdict(
        level=output.level,
        reason=truncate_display(reason, MAX_JUDGE_REASON_CHARS),
    )


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
            output_type=JudgeVerdict,
            resolve_model=False,
        )
        payload, facts = await asyncio.to_thread(_build_payload, text, cwd, sandbox_off)
        result = await asyncio.wait_for(
            agent.run(payload), timeout=JUDGE_TIMEOUT_SECONDS
        )
    except Exception as error:
        CFG.LOGGER.debug(f"Shell judge failed: {error}")
        raise ShellJudgeError(str(error) or type(error).__name__) from error
    record_agent_usage(result, component=COMPONENT_SHELL_JUDGE)
    _log_spend(result)
    verdict = verdict_from_output(getattr(result, "output", None))
    return ShellVerdict(level=verdict.level, reason=verdict.reason, facts=facts)


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


def _build_payload(command: str, cwd: str, sandbox_off: bool) -> tuple[str, str]:
    """The judge's whole input, and the risk facts worth showing a reader."""
    directory = cwd or os.getcwd()
    dirt = uncommitted_files(directory)
    sandbox = (
        "off — the command can write and reach the network anywhere"
        if sandbox_off
        else "on — writes are bounded to the workspace"
    )
    text = (
        f"Command:\n{command}\n\n"
        f"Working directory: {directory}\n"
        f"Sandbox: {sandbox}\n"
        f"Uncommitted files in this repository: {dirt}"
    )
    return text, shown_facts(dirt, sandbox_off)


def shown_facts(dirt: str, sandbox_off: bool) -> str:
    """The facts that *raise* the risk, as one line for the approval prompt.

    A sandbox that is on and a clean repository are what a reader already
    assumes, so they stay silent; the two that make a command worse are named.
    These come from the call's arguments and from `git status`, never from the
    model's sentence, so they cannot be vague.
    """
    facts: list[str] = []
    if sandbox_off:
        facts.append("sandbox off")
    if dirt.isdigit() and int(dirt) > 0:
        facts.append(f"{dirt} uncommitted")
    return " · ".join(facts)


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

    Kept beside the usage line rather than instead of it: the record answers
    `/usage` a day later, and the debug line answers a developer watching the
    judge work right now.
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
    "JudgeVerdict",
    "ShellJudgeError",
    "JUDGE_TIMEOUT_SECONDS",
    "judge_or_unknown",
    "judge_shell_command",
    "parse_verdict",
    "shown_facts",
    "verdict_from_output",
    "uncommitted_files",
    "JUDGE_CAUTION",
    "JUDGE_DANGEROUS",
    "JUDGE_SAFE",
    "JUDGE_UNKNOWN",
]

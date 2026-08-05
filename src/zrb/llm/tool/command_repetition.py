"""Counts byte-identical shell invocations so a stuck loop can be named.

``workflow.md``'s Recovery ladder says to change what you are testing by the
third attempt, or stop and report. Prose did not hold it. Across one benchmark
run every timeout was the same shape — one command re-run against one or two
files until the wall clock ran out:

=====================  =====  ===================  ========================
cell                   calls  hottest file         repeated command
=====================  =====  ===================  ========================
integration-bug t1     99     checkout.py x51      ``python3 main.py`` x24
failing-tests t1       107    text_utils.py x93    ``pytest -q`` x6
failing-tests t3       145    one path x128        ``pytest -q`` x16
=====================  =====  ===================  ========================

Every repeat was byte-identical, so a counter this simple names all three at
attempt 3 instead of 24, 6, and 16.

This lives beside the shell tool rather than in a ``tool_policy`` because
policies run in the *approval* chain: their ``next_handler`` returns the next
policy's decision, never the tool's output, so a policy physically cannot
annotate a result — an earlier attempt to do exactly that was dead code that
never emitted anything. The shell tool already owns a ``[SYSTEM SUGGESTION]``
path, so the count belongs there (ADR-0102).
"""

from __future__ import annotations

from collections import Counter
from contextvars import ContextVar

# "<cwd>\0<command>" -> attempts so far in this context.
command_attempts: ContextVar[dict[str, int]] = ContextVar(
    "command_attempts", default={}
)

# Signatures already called out, so one loop earns one escalation rather than a
# note on every later call.
command_attempts_warned: ContextVar[frozenset[str]] = ContextVar(
    "command_attempts_warned", default=frozenset()
)


def command_signature(command: str, cwd: str) -> str:
    """Identify "the same attempt".

    Deliberately exact rather than fuzzy: a model that varies its command *is*
    changing what it tests, which is the behaviour being asked for. The cwd is
    part of the identity — the same command in two directories is two tests.
    """
    return f"{cwd}\0{command.strip()}"


def record_attempt(signature: str) -> int:
    """Record another attempt at *signature* and return the new count."""
    counts = Counter(command_attempts.get())
    counts[signature] += 1
    command_attempts.set(dict(counts))
    return counts[signature]


def should_warn(signature: str, count: int, threshold: int) -> bool:
    """Whether this attempt is the one that earns the escalation."""
    if threshold <= 0 or count < threshold:
        return False
    return signature not in command_attempts_warned.get()


def mark_warned(signature: str) -> None:
    command_attempts_warned.set(command_attempts_warned.get() | {signature})


def reset_command_attempts() -> None:
    """Drop all counts. For tests and for starting a fresh session."""
    command_attempts.set({})
    command_attempts_warned.set(frozenset())

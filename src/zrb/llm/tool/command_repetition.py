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

**A repeated command is not by itself a loop.** Counting invocations alone was
wrong and shipped once: `debug-loop` asks the agent to run, fix, run, fix, run,
and every *successful* cell of that challenge — across four models — tripped the
nudge for doing exactly what the task required. Re-running a command after
changing the code is new evidence; re-running it and getting the same answer is
not. So the count keys on the **outcome**: same command, same exit code, same
output digest, consecutively. A run whose result differs from the last one
resets the streak, which is what makes an honest fix-verify loop invisible here
and a stuck one visible.

One outcome the digest cannot catch: a command whose output is nondeterministic
(a concurrency simulation reporting different numbers each run) never repeats
itself, so re-running it forever would look like progress. A second ground
covers that — same command, and no file written or edited since the last run of
it. See :func:`record_outcome`.

This lives beside the shell tool rather than in a ``tool_policy`` because
policies run in the *approval* chain: their ``next_handler`` returns the next
policy's decision, never the tool's output, so a policy physically cannot
annotate a result — an earlier attempt to do exactly that was dead code that
never emitted anything. The shell tool already owns a ``[SYSTEM SUGGESTION]``
path, so the count belongs there (ADR-0102).
"""

from __future__ import annotations

import hashlib
from contextvars import ContextVar

# "<cwd>\0<command>" -> (outcome digest, consecutive no-new-evidence runs,
# workspace revision at the time of the run).
command_attempts: ContextVar[dict[str, tuple[str, int, str]]] = ContextVar(
    "command_attempts", default={}
)

# Bumped by every successful write or edit, and — inside `record_outcome` — by
# every command run. Its only job is to answer "has *anything at all* happened
# since I last ran this?" for a command whose own output is nondeterministic and
# so can never repeat its digest. Counting other commands too keeps the second
# ground deliberately narrow: it fires only for back-to-back identical
# invocations with nothing in between, where there is no reading under which the
# second run learned something. A fix applied by `sed -i` rather than by Edit
# still counts as a change, which is the false positive worth avoiding.
workspace_revision: ContextVar[int] = ContextVar("workspace_revision", default=0)


def bump_workspace_revision() -> None:
    """Record that a file changed. Called by the write and edit tools."""
    workspace_revision.set(workspace_revision.get() + 1)


def current_workspace_state() -> str:
    return str(workspace_revision.get())


# Signatures already called out, so one loop earns one escalation rather than a
# note on every later call. Cleared for a signature whose outcome changes, so a
# command that gets unstuck and later re-sticks can be named again.
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


def outcome_digest(exit_code: str, stdout: str, stderr: str) -> str:
    """Fingerprint what a run *told* the model, which is what can go stale."""
    payload = f"{exit_code}\0{stdout.strip()}\0{stderr.strip()}"
    return hashlib.sha256(payload.encode("utf-8", "replace")).hexdigest()


def record_outcome(signature: str, digest: str) -> int:
    """Record a run and return how many consecutive runs count as no-new-evidence.

    A run is "the same again" on either of two grounds:

    * **Same outcome.** Identical exit code and output — the primary signal, and
      the one that leaves an honest fix-verify loop alone.
    * **Nothing changed in between.** Same command, and nothing at all happened
      between the previous run of it and this one. This covers the case the
      digest cannot: a nondeterministic command (a concurrency simulation whose
      numbers differ every time) never repeats its output, so re-running it
      without touching anything would otherwise look like progress forever.

    Either ground continues the streak; a run that both differs *and* follows a
    change resets it to 1.

    The revision is sampled twice, and both samples matter. The run being
    recorded is itself an event, so it bumps the counter — but comparing *this*
    run's pre-bump sample against the *previous* run's pre-bump sample would
    then always differ by exactly that bump, which made the second ground
    unreachable for its entire existence: a nondeterministic command sat at
    streak 1 forever. What gets stored is the post-bump value, so the next run
    of this signature compares the world it observed against the world as it
    stood when this run finished, and "nothing happened in between" is a
    question the two samples can actually answer.
    """
    observed = current_workspace_state()
    bump_workspace_revision()
    recorded = current_workspace_state()
    state = command_attempts.get()
    previous = state.get(signature)
    if previous is None:
        streak = 1
    else:
        prev_digest, prev_streak, prev_recorded = previous
        continues = prev_digest == digest or prev_recorded == observed
        streak = prev_streak + 1 if continues else 1
    command_attempts.set({**state, signature: (digest, streak, recorded)})
    if streak == 1:
        _clear_warned(signature)
    return streak


def should_warn(signature: str, streak: int, threshold: int) -> bool:
    """Whether this run is the one that earns the escalation."""
    if threshold <= 0 or streak < threshold:
        return False
    return signature not in command_attempts_warned.get()


def mark_warned(signature: str) -> None:
    command_attempts_warned.set(command_attempts_warned.get() | {signature})


def reset_command_attempts() -> None:
    """Drop all state. For tests and for starting a fresh session."""
    command_attempts.set({})
    command_attempts_warned.set(frozenset())
    workspace_revision.set(0)


def _clear_warned(signature: str) -> None:
    warned = command_attempts_warned.get()
    if signature in warned:
        command_attempts_warned.set(warned - {signature})

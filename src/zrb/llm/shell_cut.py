"""The send-now key moves a running command aside instead of waiting it out.

A message typed while a `Shell` call runs waits for that call to finish:
pydantic-ai delivers a steered message at the next model request, and the next
request comes after the tool returns. When the call is a long command, the wait
is the user's problem — the message sits behind work that may run for minutes.

So an explicit send-now (Ctrl+G) tells the run's in-flight shell to step aside:
the command moves to the background under a handle and the model reads the
message in the same turn. It is the same move the command's own timeout makes,
for the same reason — the work keeps going and nothing is run twice.

The signal belongs to a run, not to the process: two chat sessions in one
process steer their own turn, and one session's keypress must not move the
other's command.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar


class ShellCutSignal:
    """One run's "the user wants this turn now" flag.

    A cut carries a generation, so a waiter reacts only to a cut that happens
    *after* it started waiting: a keypress sent during an earlier tool call must
    not move a command that had not started yet.
    """

    def __init__(self) -> None:
        self._generation = 0
        self._event = asyncio.Event()

    @property
    def generation(self) -> int:
        """How many cuts this run has seen. Read it before waiting."""
        return self._generation

    def cut(self) -> None:
        """Ask every shell currently waiting in this run to step aside.

        Each cut replaces the event, so a waiter that arrives afterwards waits
        for the *next* cut and is not woken by this one a second time.
        """
        self._generation += 1
        event = self._event
        self._event = asyncio.Event()
        event.set()

    async def wait_for_cut(self, generation: int) -> None:
        """Return once this run has seen a cut newer than *generation*."""
        event = self._event
        if self._generation > generation:
            return
        await event.wait()


current_shell_cut_signal: ContextVar["ShellCutSignal | None"] = ContextVar(
    "zrb_shell_cut_signal", default=None
)


def get_run_shell_cut_signal() -> "ShellCutSignal | None":
    """The current run's cut signal, or None outside a run.

    Bound by the agent runner around `agent.run()`, like the run's limiter, so
    a tool sees the run it belongs to rather than a process-wide flag.
    """
    return current_shell_cut_signal.get()


def signal_for_run() -> ShellCutSignal:
    """The signal a starting run should bind: its parent's, else a new one.

    A delegated sub-agent, a code analysis helper and a file-reading helper all
    run inside the turn the user is trying to steer, so they share its signal
    instead of replacing it. Without this a `Shell` running inside a sub-agent
    would listen to a signal nothing ever cuts, and the key would move nothing.
    """
    return get_run_shell_cut_signal() or ShellCutSignal()


def interrupted_notice(retry: str) -> str:
    """What a monitoring call reports when a cut ended its wait.

    A wait is not work: nothing is lost by stopping it, so the call says it was
    interrupted and names the call that picks the same wait up again. The
    warning against starting a second copy is not decoration — the process or
    the sub-agent is still running.
    """
    return (
        "[interrupted] The user sent a message that needs this turn, so this "
        "wait stopped. Nothing was cancelled and nothing was lost: it is still "
        "running. Read the message first, then call "
        f"`{retry}` to wait again — do not start a second copy."
    )


async def is_cut_while_waiting(waits: "set[asyncio.Task]", seconds: float) -> bool:
    """Wait for *waits* up to *seconds*; True when a cut ended the wait first.

    The cut is the run's own (``Ctrl+G``/send-now), read the same way `Shell`
    reads it, so one session's keypress does not end another session's wait.
    Outside a run there is no signal and this is `asyncio.wait` and nothing else.
    """
    cut = get_run_shell_cut_signal()
    waiting = asyncio.ensure_future(
        asyncio.wait(waits, timeout=seconds, return_when=asyncio.ALL_COMPLETED)
    )
    if cut is None:
        await waiting
        return False
    cut_wait = asyncio.ensure_future(cut.wait_for_cut(cut.generation))
    try:
        done, _pending = await asyncio.wait(
            {waiting, cut_wait}, return_when=asyncio.FIRST_COMPLETED
        )
        return cut_wait in done
    finally:
        # Both tasks are this call's own, so reap them before returning: a
        # cancelled `asyncio.wait` left pending into the loop's next turn keeps
        # the watched tasks' done-callbacks registered, and a loop that closes
        # in between reports it as a task destroyed while still pending.
        cut_wait.cancel()
        waiting.cancel()
        await asyncio.gather(cut_wait, waiting, return_exceptions=True)

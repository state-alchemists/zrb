"""Running one capture program within a deadline."""

from __future__ import annotations

import asyncio

from zrb.llm.util.deadline import communicate_within, get_remaining

_NO_TIME_LEFT = "no time left for this capture"


class ProgramFailed(Exception):
    """A capture program did not deliver; the message says why, for the failure
    hint."""


async def run_program(
    argv: list[str], deadline: float | None, env: dict[str, str] | None = None
) -> bytes:
    """The standard output of *argv* when it exits 0 before *deadline*
    (`time.monotonic()`; ``None``: no limit). It is killed when the time runs
    out. Raises `ProgramFailed` for anything else: no time left, a program that
    will not start, a timeout, or a non-zero exit."""
    timeout = get_remaining(deadline)
    if timeout == 0:
        raise ProgramFailed(_NO_TIME_LEFT)
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except OSError as error:
        raise ProgramFailed(str(error)) from error
    try:
        stdout, stderr = await communicate_within(proc, timeout)
    except asyncio.TimeoutError:
        raise ProgramFailed(f"timed out after {timeout:.1f}s") from None
    if proc.returncode != 0:
        message = stderr.decode(errors="ignore").strip()[-500:]
        raise ProgramFailed(message or f"exited with code {proc.returncode}")
    return stdout

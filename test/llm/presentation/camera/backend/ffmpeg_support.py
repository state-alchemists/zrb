"""The two things a camera backend reaches for outside itself: a subprocess, and
ffmpeg being on the machine.

Every test beside this module fakes `asyncio.create_subprocess_exec` rather than
running ffmpeg, so `FakeProcess` carries only what the backend touches —
`communicate`, `returncode`, `kill` and `wait`. `which_only` answers
`shutil.which` with the binaries a platform is pretending to have. `record_procs`
answers both: it hands back a stand-in process and keeps every command the
backend ran, in order, so a test can assert on the path it chose and not only on
the frame it got.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock


class FakeProcess:
    "Minimal async-process stand-in for `asyncio.create_subprocess_exec`."

    def __init__(
        self,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        hang_seconds: float = 0,
    ):
        self._stdout = stdout
        self._stderr = stderr

        self._exit_code = returncode
        self.returncode: int | None = None
        self._hang_seconds = hang_seconds
        self.killed = False

    async def communicate(self):
        if self._hang_seconds:
            await asyncio.sleep(self._hang_seconds)
        self.returncode = self._exit_code
        return (self._stdout, self._stderr)

    def kill(self):
        self.killed = True
        self.returncode = -9

    async def wait(self):
        return self.returncode


def which_only(*names: str):
    'Return a `shutil.which` stand-in that only "finds" the given names.'

    def _which(name: str):
        return f"/usr/bin/{name}" if name in names else None

    return _which


def record_procs(listing: bytes = b""):
    "A `create_subprocess_exec` stand-in recording each command it runs."
    commands: list[list[str]] = []

    def _make_proc(*args, **kwargs):
        commands.append(list(args))
        if "-list_devices" in args:
            return FakeProcess(stderr=listing, returncode=1)
        return FakeProcess(stdout=b"jpeg")

    return commands, AsyncMock(side_effect=_make_proc)

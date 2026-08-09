"""Bounded capture of one subprocess stream, spilling the overflow to disk.

`run_shell_command` needs three things from a stream at once: a head-bounded
slice to hand the model, a live echo to the terminal that stops after its own
budget, and the *whole* output kept somewhere so `DumpFullOutput` can retrieve
it after the fact. Doing all three in one pass is why this is a class rather
than a helper.

Lived inside `llm/tool/shell.py` until 2.58.0, where it was 145 lines of a
620-line module and could not be tested without driving a subprocess.
"""

import os
import shutil
import tempfile
from collections import deque
from typing import TextIO

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.util.cli.style import stylize_muted


class StreamCapture:
    """Bounded capture of one output stream.

    Three budgets, deliberately separate:

    * ``retain`` — characters held in memory, tail-biased. Only the tail ever
      reached the model even before this class existed, so holding the head
      resident bought nothing.
    * ``echo`` — characters mirrored to the console. Echoing costs a regex
      substitution and a print *per line*; an unscoped ``git diff`` in a dirty
      monorepo spent longer being displayed than being computed and was killed
      by its own timeout as a result.
    * the spill file — the complete stream, written as it arrives, so the
      elided head stays recoverable without being resident.

    The spill opens exactly when the first character would be dropped, which
    keeps the invariant that ``text`` is the whole stream whenever
    ``spill_path`` is ``None``.
    """

    def __init__(self, retain: int, echo: int) -> None:
        self._retain = max(retain, 0)
        self._echo_budget = max(echo, 0)
        self._chunks: "deque[str]" = deque()
        self._held = 0
        self._echoed = 0
        self._spill: TextIO | None = None
        self._spill_failed = False
        self.total_chars = 0
        self.spill_path: str | None = None

    @property
    def text(self) -> str:
        """The retained tail — what the model is shown."""
        return "".join(self._chunks)

    @property
    def truncated(self) -> bool:
        return self.total_chars > self._held

    def feed(self, chunk: str) -> None:
        self.total_chars += len(chunk)
        if self._spill is not None:
            self._spill.write(chunk)
        self._chunks.append(chunk)
        self._held += len(chunk)
        if self._held > self._retain:
            self._begin_spill()
            self._trim()

    def echo(self, chunk: str) -> None:
        """Mirror to the console until the display budget is spent."""
        remaining = self._echo_budget - self._echoed
        if remaining <= 0:
            return
        if len(chunk) <= remaining:
            self._echoed += len(chunk)
            zrb_print(f"  {stylize_muted(chunk)}", end="", plain=True)
            return
        self._echoed = self._echo_budget
        zrb_print(f"  {stylize_muted(chunk[:remaining])}", end="", plain=True)
        zrb_print(
            stylize_muted(
                f"\n  … console output capped at {self._echo_budget} characters. "
                "The command is still being captured; only the display stops "
                f"here ({CFG.ENV_PREFIX}_LLM_MAX_CONSOLE_OUTPUT_CHARS).\n"
            ),
            end="",
            plain=True,
        )

    def write_full(self, dest: TextIO) -> None:
        """Copy the complete stream into *dest*, streaming from spill if needed."""
        if self.spill_path is None:
            dest.write(self.text)
            return
        self.close()
        with open(self.spill_path, "r", encoding="utf-8") as src:
            shutil.copyfileobj(src, dest)

    def close(self) -> None:
        if self._spill is not None:
            try:
                self._spill.close()
            except Exception as e:
                CFG.LOGGER.debug(f"Failed to close spill file: {e}")
            self._spill = None

    def discard(self) -> None:
        """Close and remove the spill file; the merged dump has superseded it."""
        self.close()
        if self.spill_path:
            try:
                os.remove(self.spill_path)
            except Exception as e:
                CFG.LOGGER.debug(f"Failed to remove spill file: {e}")
            self.spill_path = None

    def _begin_spill(self) -> None:
        """Start spilling. Best-effort: without a temp file the head is simply lost.

        Called before the first drop, when ``_chunks`` still holds everything
        received so far — so writing the deque here captures the head exactly
        once, and ``feed`` writes every later chunk directly.
        """
        if self._spill is not None or self._spill_failed:
            return
        try:
            fd, path = tempfile.mkstemp(prefix="zrb_shell_part_", suffix=".log")
            self._spill = os.fdopen(fd, "w", encoding="utf-8")
            self.spill_path = path
            self._spill.write("".join(self._chunks))
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to open spill file: {e}")
            self._spill_failed = True
            self._spill = None
            self.spill_path = None

    def _trim(self) -> None:
        """Drop from the head until the retention budget holds, tail-exact."""
        while self._chunks and self._held > self._retain:
            overflow = self._held - self._retain
            head = self._chunks.popleft()
            if len(head) > overflow:
                self._chunks.appendleft(head[overflow:])
                self._held -= overflow
                return
            self._held -= len(head)

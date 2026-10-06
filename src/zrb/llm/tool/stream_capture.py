"""Bounded capture of one subprocess stream, spilling the overflow to disk."""

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

    * ``retain`` — characters held in memory, tail-biased (only the tail
      reaches the model).
    * ``echo`` — characters mirrored to the console; echo is per-line costly,
      so it has its own, smaller budget.
    * the spill file — the complete stream, opened when the first character
      would be dropped, so ``text`` is the whole stream while ``spill_path``
      is ``None``.
    """

    def __init__(self, retain: int, echo: int, print_live: bool = True) -> None:
        self._retain = max(retain, 0)
        self._echo_budget = max(echo, 0)
        # False: `echo()` tracks the budget and `echoed_text` but doesn't
        # print, for a caller with its own live display (`update_shell_output`).
        self._print_live = print_live
        self._chunks: "deque[str]" = deque()
        self._held = 0
        self._echoed = 0
        # Unstyled copy of what `echo()` printed.
        self._echoed_chunks: list[str] = []
        self._spill: TextIO | None = None
        self._spill_failed = False
        self.total_chars = 0
        self.spill_path: str | None = None

    @property
    def text(self) -> str:
        """The retained tail — what the model is shown."""
        return "".join(self._chunks)

    @property
    def echoed_text(self) -> str:
        """Exactly what `echo()` sent to the console, unstyled."""
        return "".join(self._echoed_chunks)

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
        """Mirror to the console (if `print_live`) until the display budget is spent."""
        remaining = self._echo_budget - self._echoed
        if remaining <= 0:
            return
        if len(chunk) <= remaining:
            self._echoed += len(chunk)
            self._echoed_chunks.append(chunk)
            if self._print_live:
                zrb_print(f"  {stylize_muted(chunk)}", end="", plain=True)
            return
        self._echoed = self._echo_budget
        truncated = chunk[:remaining]
        self._echoed_chunks.append(truncated)
        if self._print_live:
            zrb_print(f"  {stylize_muted(truncated)}", end="", plain=True)
        cap_notice = (
            f"\n  … console output capped at {self._echo_budget} characters. "
            "The command is still being captured; only the display stops "
            f"here ({CFG.ENV_PREFIX}_LLM_MAX_CONSOLE_OUTPUT_CHARS).\n"
        )
        self._echoed_chunks.append(cap_notice)
        if self._print_live:
            zrb_print(stylize_muted(cap_notice), end="", plain=True)

    def write_full(self, dest: TextIO) -> None:
        """Copy the complete stream into *dest*, streaming from spill if needed."""
        if self.spill_path is None:
            dest.write(self.text)
            return
        self.close()
        with open(self.spill_path, "r", encoding="utf-8") as src:
            shutil.copyfileobj(src, dest)

    def flush(self) -> None:
        """Flush the open spill file, for callers that read it before `close()`."""
        if self._spill is not None:
            try:
                self._spill.flush()
            except Exception as e:
                CFG.LOGGER.debug(f"Failed to flush spill file: {e}")

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
        """Start spilling (best-effort), writing everything received so far."""
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

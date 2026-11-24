"""Bounded capture of one subprocess stream, spilling the overflow to disk."""

import os
import shutil
import tempfile
from collections import deque
from typing import TextIO

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.util.cli.style import stylize_muted

#: Characters a capped spill file holds before it stops accepting more. A
#: background process has no deadline, so without a cap the file could grow for
#: as long as the process runs. The in-memory tail and `total_chars` are not
#: affected. A foreground capture is bounded by its command's timeout and is
#: created uncapped, so its dump is the whole stream.
SPILL_MAX_CHARS = 256 * 1024 * 1024


class StreamCapture:
    """Bounded capture of one output stream.

    * ``retain`` — characters held in memory, tail-biased (only the tail
      reaches the model).
    * ``echo`` — characters mirrored to the console; echo is per-line costly,
      so it has its own, smaller budget.
    * the spill file — the complete stream, opened when the first character
      would be dropped, so ``text`` is the whole stream while ``spill_path``
      is ``None``. With ``cap_spill`` its size stops at `SPILL_MAX_CHARS` and
      the capture records why, while the tail stays in memory; without it the
      file grows until the stream ends.
    """

    def __init__(
        self,
        retain: int,
        echo: int,
        print_live: bool = True,
        cap_spill: bool = True,
    ) -> None:
        self._retain = max(retain, 0)
        self._echo_budget = max(echo, 0)
        self._cap_spill = cap_spill
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
        self._spilled = 0
        self._spill_capped = False
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

    @property
    def is_spill_capped(self) -> bool:
        """Whether the spill file stopped at `SPILL_MAX_CHARS`."""
        return self._spill_capped

    @property
    def spill_max_chars(self) -> int | None:
        """The character cap for the spill file, or None when it is uncapped."""
        return SPILL_MAX_CHARS if self._cap_spill else None

    def head_text(self, limit: int) -> str:
        """The first *limit* characters of the stream, read back from the spill.

        Empty when nothing was dropped — ``text`` is already the whole stream —
        or when the spill is unavailable: a missing head costs the caller an
        excerpt, never the output.
        """
        if limit <= 0 or not self.truncated or self.spill_path is None:
            return ""
        self.flush()
        try:
            with open(self.spill_path, "r", encoding="utf-8", errors="replace") as src:
                return src.read(limit)
        except OSError as e:
            CFG.LOGGER.debug(f"Failed to read the head of the stream: {e}")
            return ""

    def feed(self, chunk: str) -> None:
        self.total_chars += len(chunk)
        self._write_to_spill(chunk)
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
            self._write_to_spill("".join(self._chunks))
        except Exception as e:
            CFG.LOGGER.debug(f"Failed to open spill file: {e}")
            self._spill_failed = True
            self._spill = None
            self.spill_path = None

    def _write_to_spill(self, text: str) -> None:
        """Append *text* to the spill file, stopping at the cap when it has one.

        `total_chars` and the in-memory tail keep working past the cap; only
        the on-disk copy stops, and the file says why so a later reader does
        not mistake a capped file for the whole stream.
        """
        if self._spill is None or self._spill_capped or not text:
            return
        if not self._cap_spill:
            self._spill.write(text)
            self._spilled += len(text)
            return
        remaining = SPILL_MAX_CHARS - self._spilled
        if remaining <= 0:
            self._record_spill_cap()
            return
        written = text[:remaining]
        self._spill.write(written)
        self._spilled += len(written)
        if len(written) < len(text):
            self._record_spill_cap()

    def _record_spill_cap(self) -> None:
        """Mark the spill file capped, leaving the reason inside it."""
        if self._spill_capped:
            return
        self._spill_capped = True
        if self._spill is None:
            return
        self._spill.write(
            f"\n[spill file capped at {SPILL_MAX_CHARS} characters; "
            "later output was not saved to disk]\n"
        )

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

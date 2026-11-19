"""What `run_command` keeps, prints and counts while output streams past.

Two limits bound a child's output, and each is a single comparison away from
the wrong behaviour:

- `CFG.CMD_BUFFER_LIMIT` bounds one *unterminated* line, so a child that never
  prints a newline cannot grow the parent's buffer without end;
- `max_output_line` bounds how many *trailing* lines the result retains.

A wrong comparison here is not cosmetic. Splitting a line that merely reaches
the bound puts a newline in `result.output` that the command never printed, and
a cap that miscounts tells the user about lines that were never dropped. So
each test sits on its boundary rather than safely inside it.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.cmd.cmd_result import CmdResult
from zrb.cmd.command import run_command
from zrb.config.config import CFG


def _stream(*chunks: bytes) -> MagicMock:
    """A reader that yields *chunks* and then reports end-of-file."""
    stream = MagicMock()
    stream.read = AsyncMock(side_effect=[*chunks, b""])
    return stream


async def _run(
    *stdout_chunks: bytes, stderr: bytes = b"", **kwargs
) -> tuple[CmdResult, list[str]]:
    """Run one fake child that reads out these chunks, and then exits."""
    process = MagicMock()
    process.pid = 999
    process.returncode = 0
    process.stdout = _stream(*stdout_chunks)
    process.stderr = _stream(stderr)
    process.wait = AsyncMock(return_value=0)
    printed: list[str] = []
    with patch(
        "zrb.cmd.command.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=process),
    ):
        result, return_code = await run_command(
            ["irrelevant"], print_method=printed.append, **kwargs
        )
    assert return_code == 0
    return result, printed


@pytest.mark.asyncio
async def test_a_line_of_exactly_the_bound_is_still_one_line(monkeypatch):
    """The bound means *more* than this many characters, not *this many*.

    The line reaches the bound in one chunk and is completed by the next. Held,
    the two halves come back as one line; split at the bound, a command that
    printed one long line is reported as two.
    """
    monkeypatch.setattr(CFG, "CMD_BUFFER_LIMIT", 10)

    result, printed = await _run(b"a" * 10, b"b" * 5)

    assert result.output == "a" * 10 + "b" * 5
    assert printed == ["a" * 10 + "b" * 5]


@pytest.mark.asyncio
async def test_a_chunk_holding_two_lines_is_printed_line_by_line():
    """Live output is what makes a long command bearable: each complete line
    goes out as it arrives, not in one lump once the stream ends."""
    result, printed = await _run(b"one\ntwo\n")

    assert printed == ["one", "two"]
    assert result.output == "one\ntwo"


@pytest.mark.asyncio
async def test_a_partial_character_at_the_end_is_flushed_not_dropped():
    """A stream may end mid-character; the bytes already decoded would vanish
    with it, so the final decode reports them as the replacement character."""
    result, _ = await _run(b"caf\xc3")

    assert result.output == "caf\ufffd"


@pytest.mark.asyncio
async def test_the_cap_keeps_the_last_lines_and_counts_what_it_dropped():
    """The cap evicts from the front, and the notice says how many went."""
    result, printed = await _run(b"a\nb\nc\n", max_output_line=2)

    assert result.output == "b\nc"
    assert any(
        "dropped 1 stdout line(s), keeping the last 2" in message for message in printed
    )


@pytest.mark.asyncio
async def test_a_cap_of_zero_keeps_every_line_and_reports_nothing():
    """Zero is the documented way to keep everything, so it never drops a line
    and never prints the notice that would tell the user it had."""
    result, printed = await _run(b"a\nb\nc\n", max_output_line=0)

    assert result.output == "a\nb\nc"
    assert not any("dropped" in message for message in printed)

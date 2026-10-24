import asyncio
import gc
import warnings
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.tool import shell as shell_mod
from zrb.llm.tool.shell import run_shell_command


class _MockStreamReader:
    """Fake asyncio.StreamReader that yields preset lines then EOF."""

    def __init__(self, lines: list[bytes]):
        self._lines = lines
        self._pos = 0

    async def readline(self) -> bytes:
        if self._pos < len(self._lines):
            line = self._lines[self._pos]
            self._pos += 1
            return line
        return b""

    def at_eof(self) -> bool:
        return self._pos >= len(self._lines)

    async def read(self) -> bytes:
        """The rest of the stream, as the background registry reads it."""
        remaining = b"".join(self._lines[self._pos :])
        self._pos = len(self._lines)
        return remaining


def _make_mock_process(
    stdout_lines: list[str] | None = None,
    stderr_lines: list[str] | None = None,
    returncode: int = 0,
    pid: int = 12345,
) -> MagicMock:
    """Build a mock asyncio.subprocess.Process with readable streams."""
    proc = MagicMock()
    proc.stdout = _MockStreamReader(
        [(s.encode() if isinstance(s, str) else s) for s in (stdout_lines or [])]
    )
    proc.stderr = _MockStreamReader(
        [(s.encode() if isinstance(s, str) else s) for s in (stderr_lines or [])]
    )
    proc.wait = AsyncMock(return_value=returncode)
    proc.returncode = returncode
    proc.pid = pid
    return proc


class _InterleavingStreamReader:
    """Like `_MockStreamReader`, but yields control between lines so two
    concurrent `run_shell_command()` calls genuinely interleave — matching
    real concurrent subprocess execution (confirmed: pydantic-ai runs
    same-turn tool calls as concurrent asyncio tasks)."""

    def __init__(self, lines: list[bytes]):
        self._lines = lines
        self._pos = 0

    async def readline(self) -> bytes:
        await asyncio.sleep(0)
        if self._pos < len(self._lines):
            line = self._lines[self._pos]
            self._pos += 1
            return line
        return b""


@pytest.mark.asyncio
async def test_shell_output_collapse_swallows_a_broken_uis_exception(
    monkeypatch, caplog
):
    """Ignore UI hook failures while logging both live and final failures."""
    mock_ui = MagicMock()
    mock_ui.update_shell_output.side_effect = RuntimeError("ui exploded")
    mock_ui.finish_shell_output.side_effect = RuntimeError("ui exploded")
    monkeypatch.setattr(shell_mod, "get_current_ui", lambda: mock_ui)
    mock_proc = _make_mock_process(stdout_lines=["hello\n"])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )

    with caplog.at_level("DEBUG"):
        res = await run_shell_command("emit", shell="node")  # must not raise

    assert "hello" in res
    assert "Live shell output push failed: ui exploded" in caplog.text
    assert "Final shell output capture failed: ui exploded" in caplog.text


@pytest.mark.asyncio
async def test_two_parallel_shell_calls_each_get_their_own_collapsible_block(
    monkeypatch,
):
    """Keep interleaved output from parallel commands in separate blocks."""
    # lazy: only this test needs a real UI implementation
    from zrb.llm.ui.buffered_ui import BufferedUI

    ui = BufferedUI(MagicMock())
    monkeypatch.setattr(shell_mod, "get_current_ui", lambda: ui)

    def _interleaving_process(lines: list[str]) -> MagicMock:
        proc = MagicMock()
        proc.stdout = _InterleavingStreamReader([line.encode() for line in lines])
        proc.stderr = _InterleavingStreamReader([])
        proc.wait = AsyncMock(return_value=0)
        proc.returncode = 0
        proc.pid = 12345
        return proc

    dog_lines = [f"dog {i}\n" for i in range(1, 6)]
    cat_lines = [f"cat {i}\n" for i in range(1, 6)]
    calls = iter([_interleaving_process(dog_lines), _interleaving_process(cat_lines)])
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=lambda *a, **kw: next(calls)),
    )

    await asyncio.gather(
        run_shell_command("dog-loop", shell="bash"),
        run_shell_command("cat-loop", shell="bash"),
    )

    assert len(ui.rendered_blocks) == 2, "each command must get its own block"
    fulls = {block[2].full for block in ui.rendered_blocks}
    assert any(
        all(f"dog {i}" in f for i in range(1, 6)) for f in fulls
    ), "dog's own lines must all be in ONE of the two blocks"
    assert any(
        all(f"cat {i}" in f for i in range(1, 6)) for f in fulls
    ), "cat's own lines must all be in the OTHER block, not swallowed by dog's"


async def _cancel_mock_background(monkeypatch) -> None:
    """Release what a mock process left in the registry, without signalling.

    The mocked process shares a fake pid with every other mock here, so the
    real kill path must not run.
    """
    # lazy: only the backgrounded-timeout tests need the registry
    from zrb.llm.tool import shell_background

    monkeypatch.setattr(shell_background, "terminate_process", AsyncMock())
    await shell_background.get_shell_background_registry().cancel_all()


@pytest.mark.asyncio
async def test_a_flooded_command_that_times_out_is_moved_not_called_hung(monkeypatch):
    """A command cut off mid-write was not waiting on stdin.

    The old suggestion sent the model to `ps aux | grep` for a process that had
    been killed, and never named the actual remedy — bounding the output. Now
    nothing is killed at the timeout: the command is neither hung nor dead, it
    is still writing, in the background, and the report says so.
    """
    monkeypatch.setattr(CFG, "LLM_MAX_OUTPUT_CHARS", 50)

    async def _never_finishes(*args, **kwargs):
        await asyncio.sleep(10)

    mock_proc = _make_mock_process(stdout_lines=[f"x-{i:05d}\n" for i in range(400)])
    mock_proc.wait = _never_finishes
    mock_proc.returncode = None
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    )
    monkeypatch.setattr(shell_mod, "terminate_process", AsyncMock())

    try:
        res = await run_shell_command("emit", shell="node", timeout=1)
    finally:
        await _cancel_mock_background(monkeypatch)

    assert "(moved to background after 1s)" in res
    assert "kept the beginning and the end" in res
    assert "still writing, not waiting on input" not in res
    assert "ps aux" not in res


@pytest.mark.asyncio
async def test_timeout_without_output_still_reads_as_a_possible_hang(monkeypatch):
    """The quiet timeout keeps the original diagnosis — nothing was produced."""
    monkeypatch.setattr(shell_mod, "terminate_process", AsyncMock())

    res = await run_shell_command("sleep 5", timeout=1)

    assert "(timed out)" in res
    assert "ps aux" in res
    assert "still writing" not in res


def test_docstring_routes_file_work_to_the_file_tools():
    """The Shell schema routes file operations to the file tools."""
    doc = run_shell_command.__doc__ or ""

    for file_tool in ("Read", "Write", "Edit", "Grep", "Glob", "LS", "RM", "MV"):
        assert file_tool in doc
    for wrong in ("cat", "find", "sed -i"):
        assert wrong in doc

    assert "not Bash" in doc


@pytest.mark.asyncio
async def test_a_timed_out_command_leaves_no_unclosed_transport():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await run_shell_command("sleep 5", timeout=1)
        gc.collect()

    leaked = [str(w.message) for w in caught if "unclosed transport" in str(w.message)]
    assert leaked == []


def _noisy_lines(first: str, last: str, filler: int = 60) -> list[str]:
    return [first] + [f"line-{index:04d}\n" for index in range(filler)] + [last]


async def _run_noisy(monkeypatch, lines: list[str], returncode: int, max_chars: int):
    monkeypatch.setattr(
        shell_mod.asyncio,
        "create_subprocess_exec",
        AsyncMock(
            return_value=_make_mock_process(stdout_lines=lines, returncode=returncode)
        ),
    )
    return await run_shell_command("noisy", shell="node", max_chars=max_chars)


@pytest.mark.asyncio
async def test_a_failed_command_shows_its_first_line_and_its_last(monkeypatch):
    """A failure announces its cause first and summarizes it last, so the
    tail-only excerpt — right for a result — hides why it failed."""
    res = await _run_noisy(
        monkeypatch, _noisy_lines("FIRST-CAUSE\n", "LAST-SUMMARY\n"), 1, 200
    )

    assert "FIRST-CAUSE" in res
    assert "LAST-SUMMARY" in res
    assert "characters elided" in res
    assert "kept the beginning and the end" in res


@pytest.mark.asyncio
async def test_a_successful_command_still_keeps_only_its_tail(monkeypatch):
    """The result of a command that worked is at its end; the beginning is
    progress chatter nobody needs to read again."""
    res = await _run_noisy(
        monkeypatch, _noisy_lines("FIRST-LINE\n", "LAST-RESULT\n"), 0, 200
    )

    assert "LAST-RESULT" in res
    assert "FIRST-LINE" not in res
    assert "characters elided" not in res
    assert "kept the tail" in res


@pytest.mark.asyncio
async def test_a_failure_that_fits_is_shown_whole(monkeypatch):
    res = await _run_noisy(
        monkeypatch,
        _noisy_lines("FIRST-CAUSE\n", "LAST-SUMMARY\n", filler=2),
        1,
        10_000,
    )

    assert "FIRST-CAUSE" in res
    assert "LAST-SUMMARY" in res
    assert "characters elided" not in res
    assert "Output truncated" not in res

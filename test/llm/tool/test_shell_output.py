import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.config.config import CFG
from zrb.llm.tool import shell as shell_mod
from zrb.llm.tool import stream_capture as capture_mod
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
async def test_shell_output_collapse_swallows_a_broken_uis_exception(monkeypatch):
    """A UI whose hooks raise must never break the actual command — same
    contract as `_notify`'s broken-UI test."""
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

    res = await run_shell_command("emit", shell="node")  # must not raise

    assert "hello" in res


@pytest.mark.asyncio
async def test_two_parallel_shell_calls_each_get_their_own_collapsible_block(
    monkeypatch,
):
    """The actual bug reported: two Shell commands running in parallel had
    their genuinely-interleaved live output collapse into ONE combined
    block, silently swallowing one command's lines. Runs two REAL
    `run_shell_command()` calls concurrently through a real `BufferedUI` —
    not mocks — so this fails the same way the live TUI did if the
    per-command isolation regresses.
    """
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


@pytest.mark.asyncio
async def test_timeout_after_flooding_is_not_diagnosed_as_a_hang(monkeypatch):
    """A command killed mid-write was not waiting on stdin.

    The old suggestion sent the model to `ps aux | grep` for a process that was
    already dead, and never named the actual remedy — bounding the output.
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

    res = await run_shell_command("emit", shell="node", timeout=1)

    assert "(timed out)" in res
    assert "still writing, not waiting on input" in res
    assert "--stat" in res
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
    """Shell must say it is for running things, not for touching files.

    A model that reaches for `cat`/`sed -i`/`rm` gets none of what the file tools
    carry — post-write diagnostics, path validation, per-path auto-approval — so
    the routing rule belongs next to the schema it competes with, not only in the
    prompt where it applies to no tool in particular. It must also say to call
    Shell rather than Bash — Bash is no longer a tool, so the docstring is the
    only place the model learns that sub-agents listing `Bash` map to Shell.
    """
    doc = run_shell_command.__doc__ or ""

    for file_tool in ("Read", "Write", "Edit", "Grep", "Glob", "LS", "RM", "MV"):
        assert file_tool in doc
    for wrong in ("cat", "find", "sed -i"):
        assert wrong in doc

    assert "not Bash" in doc

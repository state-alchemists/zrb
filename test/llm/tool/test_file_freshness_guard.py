"""The stale-overwrite guard, exercised through the tools that enforce it.

This was a ``tool_policy`` first. Across 125 benchmark cells it refused nothing:
``check_tool_policies`` is only reached when ``effective_tool_confirmation``
resolves to a ``ToolCallHandler``, which a ``--interactive false`` run does not
bind — so the guard evaporated in exactly the mode the benchmark used, while its
unit tests kept passing. Driving the real tools is what makes that impossible to
repeat.
"""

import pytest

from zrb.llm.tool.file_edit import replace_in_file
from zrb.llm.tool.file_freshness import reset_file_freshness
from zrb.llm.tool.file_read import read_file
from zrb.llm.tool.file_write import write_file

_BODY = "def run():\n    return\n"


@pytest.fixture(autouse=True)
def _clean_state():
    reset_file_freshness()
    yield
    reset_file_freshness()


@pytest.fixture
def target(tmp_path):
    p = tmp_path / "worker.py"
    p.write_text(_BODY)
    return p


@pytest.mark.asyncio
async def test_creating_a_new_file_is_never_blocked(tmp_path):
    """Nothing to be stale about when the path does not exist yet."""
    result = await write_file(str(tmp_path / "new.py"), "x = 1\n")

    assert result.startswith("Successfully wrote")


@pytest.mark.asyncio
async def test_overwriting_an_unread_file_is_refused(target):
    """A whole-file write replaces content this call never names."""
    result = await write_file(str(target), "x = 1\n")

    assert result.startswith("Refused:")
    assert "have not read it" in result
    assert "Edit" in result
    assert target.read_text() == _BODY, "the refusal must not have written"


@pytest.mark.asyncio
async def test_write_is_allowed_after_a_full_read(target):
    read_file(str(target))

    result = await write_file(str(target), "x = 1\n")

    assert result.startswith("Successfully wrote")


@pytest.mark.asyncio
async def test_a_partial_read_does_not_grant_a_whole_file_write(tmp_path):
    """A window into a file is not a view of it.

    The rule is about what the model can be sure it is replacing, and 20 lines
    of a 400-line file says nothing about the other 380.
    """
    big = tmp_path / "big.py"
    big.write_text("".join(f"line_{i} = {i}\n" for i in range(400)))

    read_file(str(big), 1, 20)
    result = await write_file(str(big), "x = 1\n")

    assert result.startswith("Refused:")


@pytest.mark.asyncio
async def test_an_edit_makes_a_later_blind_write_stale(target):
    """The regression this guard exists for.

    A trial read worker.py, edited it, got a [DIAGNOSTIC], and rewrote the whole
    file from memory — reverting the edit and shipping an infinite loop. It had
    read the file, so read-before-write alone would have allowed it. The read
    has to postdate the change.
    """
    read_file(str(target))
    await replace_in_file(str(target), "return", "continue")

    result = await write_file(str(target), _BODY)

    assert result.startswith("Refused:")
    assert "changed since you last read it" in result


@pytest.mark.asyncio
async def test_rereading_clears_staleness(target):
    read_file(str(target))
    await replace_in_file(str(target), "return", "continue")
    read_file(str(target))

    result = await write_file(str(target), "x = 1\n")

    assert result.startswith("Successfully wrote")


@pytest.mark.asyncio
async def test_consecutive_writes_are_allowed(tmp_path):
    """The model authored every byte of the previous write; its memory is the file."""
    p = tmp_path / "gen.py"

    await write_file(str(p), "first = 1\n")
    result = await write_file(str(p), "second = 2\n")

    assert result.startswith("Successfully wrote")


@pytest.mark.asyncio
async def test_appending_is_never_gated(target):
    """Append adds to whatever is there; it cannot discard it."""
    result = await write_file(str(target), "# tail\n", mode="a")

    assert result.startswith("Successfully wrote")
    assert _BODY in target.read_text()


@pytest.mark.asyncio
async def test_edit_is_never_gated(target):
    """old_text already fails loudly on drift; a precondition would be friction."""
    result = await replace_in_file(str(target), "return", "pass")

    assert result.startswith("Successfully updated")


@pytest.mark.asyncio
async def test_the_guard_needs_no_approval_channel(target):
    """It must hold in headless mode, which is where the policy version died.

    Nothing in this test binds a UI, an approval channel, or a
    ToolCallHandler — the same shape as `zrb chat --interactive false`.
    """
    result = await write_file(str(target), "x = 1\n")

    assert result.startswith("Refused:")


@pytest.mark.asyncio
async def test_a_blind_edit_streak_is_named(tmp_path, monkeypatch):
    """The gap that timed out a cell: 59 edits to one file, nothing else.

    No shell run and no diagnostic, so neither the repeated-command counter
    (shell-only) nor the post-write escalation (diagnostic-gated) could see it.
    """
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_BLIND_EDIT_STREAK_THRESHOLD", 3)
    p = tmp_path / "loop.py"
    p.write_text("a = 1\nb = 2\nc = 3\n")

    await replace_in_file(str(p), "a = 1", "a = 10")
    await replace_in_file(str(p), "b = 2", "b = 20")
    third = await replace_in_file(str(p), "c = 3", "c = 30")

    assert "3 edits in a row" in third
    assert "nothing read and nothing run" in third


@pytest.mark.asyncio
async def test_reading_the_file_breaks_the_streak(tmp_path, monkeypatch):
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_BLIND_EDIT_STREAK_THRESHOLD", 3)
    p = tmp_path / "loop.py"
    p.write_text("a = 1\nb = 2\nc = 3\n")

    await replace_in_file(str(p), "a = 1", "a = 10")
    await replace_in_file(str(p), "b = 2", "b = 20")
    read_file(str(p))
    third = await replace_in_file(str(p), "c = 3", "c = 30")

    assert "edits in a row" not in third


@pytest.mark.asyncio
async def test_editing_many_files_is_not_a_streak(tmp_path, monkeypatch):
    """A 44-site migration makes hundreds of edits — across dozens of paths.

    Consecutiveness on ONE path is what separates a loop from breadth.
    """
    from zrb.config.config import CFG

    monkeypatch.setattr(CFG, "LLM_BLIND_EDIT_STREAK_THRESHOLD", 3)
    results = []
    for i in range(6):
        f = tmp_path / f"m{i}.py"
        f.write_text("legacy_auth()\n")
        results.append(await replace_in_file(str(f), "legacy_auth", "new_auth"))

    assert all("edits in a row" not in r for r in results)


@pytest.mark.asyncio
async def test_a_shell_command_breaks_every_streak(tmp_path, monkeypatch):
    """Running anything is evidence for the whole workspace, not one file."""
    from zrb.config.config import CFG
    from zrb.llm.tool.shell import run_shell_command

    monkeypatch.setattr(CFG, "LLM_BLIND_EDIT_STREAK_THRESHOLD", 3)
    p = tmp_path / "loop.py"
    p.write_text("a = 1\nb = 2\nc = 3\n")

    await replace_in_file(str(p), "a = 1", "a = 10")
    await replace_in_file(str(p), "b = 2", "b = 20")
    await run_shell_command("echo checked")
    third = await replace_in_file(str(p), "c = 3", "c = 30")

    assert "edits in a row" not in third

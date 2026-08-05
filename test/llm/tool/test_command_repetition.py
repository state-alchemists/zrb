"""The repeated-outcome counter, exercised through the shell tool that owns it.

Two shapes this must keep apart, both drawn from benchmark runs:

* A **stuck loop** — one command re-run until the clock ran out (``pytest -q``
  x16, ``python3 main.py`` x24). Worth naming.
* An **honest fix-verify loop** — ``debug-loop``'s run → fix → run → fix → run.
  An earlier version counted invocations, so every *successful* cell of that
  challenge, across four models, tripped the nudge for doing what the task
  required. Keying on the outcome is what tells the two apart.

An even earlier version lived in a ``tool_policy``, where ``next_handler``
returns the next policy's decision rather than the tool's output, so the note
was appended to ``None`` and dropped on every call. These tests drive the real
tool so neither shape can come back.
"""

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.command_repetition import reset_command_attempts
from zrb.llm.tool.file_write import write_file
from zrb.llm.tool.shell import run_shell_command

_NUDGE = "told you nothing new"


@pytest.fixture(autouse=True)
def _clean_state():
    reset_command_attempts()
    yield
    reset_command_attempts()


@pytest.mark.asyncio
async def test_the_first_repeats_are_left_alone():
    """Re-running a suite twice is ordinary; only a stuck streak is worth naming."""
    first = await run_shell_command("echo one")
    second = await run_shell_command("echo one")

    assert _NUDGE not in first
    assert _NUDGE not in second


@pytest.mark.asyncio
async def test_the_third_identical_outcome_is_named():
    for _ in range(2):
        await run_shell_command("echo loop")
    third = await run_shell_command("echo loop")

    assert _NUDGE in third
    assert "3 times in a row" in third
    assert "stop and report" in third


@pytest.mark.asyncio
async def test_a_fix_verify_loop_is_not_a_stuck_loop(tmp_path):
    """The regression that shipped: run → fix → run → fix → run must stay silent.

    Same command every time, different result every time — which is precisely
    what progress looks like. ``debug-loop`` requires this, and every passing
    cell of it was being told to stop.
    """
    script = tmp_path / "run.sh"
    marker = tmp_path / "stage"
    script.write_text(f'cat "{marker}"\n')
    cmd = f'sh "{script}"'

    results = []
    for stage in ("error one", "error two", "success"):
        await write_file(str(marker), stage + "\n")
        results.append(await run_shell_command(cmd))

    assert all(_NUDGE not in r for r in results)
    assert "success" in results[-1]


@pytest.mark.asyncio
async def test_a_changed_outcome_resets_the_streak(tmp_path):
    """Two stuck runs, then progress, then two more: no nudge at any point."""
    marker = tmp_path / "out"
    await write_file(str(marker), "same\n")  # via the tool, so it stays writable
    cmd = f'cat "{marker}"'

    await run_shell_command(cmd)
    second = await run_shell_command(cmd)
    await write_file(str(marker), "different\n")
    third = await run_shell_command(cmd)
    fourth = await run_shell_command(cmd)

    assert all(_NUDGE not in r for r in (second, third, fourth))


@pytest.mark.asyncio
async def test_a_restuck_command_can_be_named_again(tmp_path):
    """Getting unstuck clears the warning, so a later stall is still reported."""
    marker = tmp_path / "out"
    await write_file(str(marker), "stuck\n")  # via the tool, so it stays writable
    cmd = f'cat "{marker}"'

    first_streak = [await run_shell_command(cmd) for _ in range(3)]
    await write_file(str(marker), "moved\n")
    second_streak = [await run_shell_command(cmd) for _ in range(3)]

    assert any(_NUDGE in r for r in first_streak)
    assert any(_NUDGE in r for r in second_streak)


@pytest.mark.asyncio
async def test_the_note_fires_once_per_streak():
    for _ in range(3):
        await run_shell_command("echo loop")
    fourth = await run_shell_command("echo loop")

    assert _NUDGE not in fourth


@pytest.mark.asyncio
async def test_a_varied_command_is_not_a_repeat():
    await run_shell_command("echo a")
    await run_shell_command("echo b")
    third = await run_shell_command("echo c")

    assert _NUDGE not in third


@pytest.mark.asyncio
async def test_the_same_command_in_another_directory_is_another_test(tmp_path):
    """``pytest -q`` in two packages is two tests, not one repeated attempt."""
    other = tmp_path / "elsewhere"
    other.mkdir()
    for _ in range(2):
        await run_shell_command("echo scoped")
    third = await run_shell_command("echo scoped", cwd=str(other))

    assert _NUDGE not in third


@pytest.mark.asyncio
async def test_the_command_still_runs_and_keeps_its_output():
    """The note is additive — it never replaces or blocks the result."""
    for _ in range(2):
        await run_shell_command("echo payload")
    third = await run_shell_command("echo payload")

    assert "payload" in third
    assert "Exit Code: 0" in third
    assert _NUDGE in third


@pytest.mark.asyncio
async def test_the_note_coexists_with_a_failure_suggestion():
    """A command can both fail recognizably and be the third identical outcome."""
    for _ in range(2):
        await run_shell_command("nonexistent-binary-xyz")
    third = await run_shell_command("nonexistent-binary-xyz")

    assert "command not found" in third.lower()
    assert _NUDGE in third


@pytest.mark.asyncio
async def test_a_zero_threshold_disables_it(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_REPEATED_ATTEMPT_THRESHOLD", 0)

    for _ in range(5):
        result = await run_shell_command("echo off")

    assert _NUDGE not in result


@pytest.mark.asyncio
async def test_bash_shares_the_counter():
    """Bash delegates to the shell tool, so the streak must not fork."""
    from zrb.llm.tool.bash import run_bash_command

    await run_shell_command("echo shared")
    await run_bash_command("echo shared")
    third = await run_bash_command("echo shared")

    assert _NUDGE in third


@pytest.mark.asyncio
async def test_background_launches_are_not_counted(monkeypatch):
    """A backgrounded process returns a handle, not a result to loop on."""

    class _Registry:
        async def start(self, *args, **kwargs):
            return "h1"

    monkeypatch.setattr(
        "zrb.llm.tool.shell_background.get_shell_background_registry",
        lambda: _Registry(),
    )
    for _ in range(3):
        result = await run_shell_command("sleep 1", background=True)

    assert _NUDGE not in result


@pytest.mark.asyncio
async def test_a_nondeterministic_command_rerun_for_nothing_is_named(
    monkeypatch, tmp_path
):
    """The second ground, which was unreachable for its entire existence.

    A command whose output differs every run — a concurrency simulation
    reporting different numbers — can never repeat its digest, so re-running it
    forever looked like progress. The fallback ground was "same command, and
    nothing happened in between", but the run's own workspace-revision bump was
    sampled on the wrong side of itself, so consecutive runs always looked one
    change apart and the streak sat at 1 no matter how many times it ran.
    """
    script = tmp_path / "sim.py"
    script.write_text("import random\nprint(random.random())\n")
    cmd = f"python3 {script}"

    first = await run_shell_command(cmd, cwd=str(tmp_path))
    second = await run_shell_command(cmd, cwd=str(tmp_path))
    third = await run_shell_command(cmd, cwd=str(tmp_path))

    assert _NUDGE not in first
    assert _NUDGE not in second
    assert _NUDGE in third
    assert "no file changed since the previous run" in third


@pytest.mark.asyncio
async def test_editing_a_file_between_nondeterministic_runs_resets_it(tmp_path):
    """A write in between is new evidence even when the output never repeats.

    This is what keeps the second ground off an honest loop: the digest cannot
    vouch for a nondeterministic command, so the file change has to.
    """
    script = tmp_path / "sim.py"
    script.write_text("import random\nprint(random.random())\n")
    cmd = f"python3 {script}"
    target = tmp_path / "fix.py"

    results = []
    for i in range(4):
        results.append(await run_shell_command(cmd, cwd=str(tmp_path)))
        await write_file(str(target), f"attempt = {i}\n")

    assert all(_NUDGE not in r for r in results)

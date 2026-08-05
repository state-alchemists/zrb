"""The repeated-attempt counter, exercised through the shell tool that owns it.

An earlier version of this lived in a ``tool_policy``. Policies run in the
*approval* chain — ``next_handler`` returns the next policy's decision, never
the tool's output — so the note was appended to ``None`` and silently dropped
on every call. These tests drive the real tool so that shape cannot come back.
"""

import pytest

from zrb.config.config import CFG
from zrb.llm.tool.command_repetition import reset_command_attempts
from zrb.llm.tool.shell import run_shell_command


@pytest.fixture(autouse=True)
def _clean_state():
    reset_command_attempts()
    yield
    reset_command_attempts()


@pytest.mark.asyncio
async def test_the_first_attempts_are_left_alone():
    """Re-running a suite twice is ordinary; only a loop is worth naming."""
    first = await run_shell_command("echo one")
    second = await run_shell_command("echo one")

    assert "[SYSTEM SUGGESTION]" not in first
    assert "[SYSTEM SUGGESTION]" not in second


@pytest.mark.asyncio
async def test_the_third_identical_attempt_is_named():
    """All three benchmark timeouts re-ran one command 6, 16, and 24 times."""
    for _ in range(2):
        await run_shell_command("echo loop")
    third = await run_shell_command("echo loop")

    assert "attempt 3 at this exact command" in third
    assert "stop and report" in third


@pytest.mark.asyncio
async def test_the_note_fires_once_not_on_every_later_call():
    """One loop earns one escalation; nagging would be noise inside the noise."""
    for _ in range(3):
        await run_shell_command("echo loop")
    fourth = await run_shell_command("echo loop")

    assert "[SYSTEM SUGGESTION]" not in fourth


@pytest.mark.asyncio
async def test_a_varied_command_is_not_a_repeat():
    """Varying the command IS changing what you test — the desired behaviour."""
    await run_shell_command("echo a")
    await run_shell_command("echo b")
    third = await run_shell_command("echo c")

    assert "[SYSTEM SUGGESTION]" not in third


@pytest.mark.asyncio
async def test_the_same_command_in_another_directory_is_another_test(tmp_path):
    """`pytest -q` in two packages is two tests, not one repeated attempt."""
    other = tmp_path / "elsewhere"
    other.mkdir()
    for _ in range(2):
        await run_shell_command("echo scoped")
    third = await run_shell_command("echo scoped", cwd=str(other))

    assert "[SYSTEM SUGGESTION]" not in third


@pytest.mark.asyncio
async def test_the_command_still_runs_and_keeps_its_output():
    """The note is additive — it never replaces or blocks the result."""
    for _ in range(2):
        await run_shell_command("echo payload")
    third = await run_shell_command("echo payload")

    assert "payload" in third
    assert "Exit Code: 0" in third
    assert "attempt 3" in third


@pytest.mark.asyncio
async def test_the_note_coexists_with_a_failure_suggestion():
    """A command can both fail recognizably and be the third identical attempt.

    The failure hint is chosen by an if/elif chain; the loop observation is
    appended separately, because the second one is what breaks the loop.
    """
    for _ in range(2):
        await run_shell_command("nonexistent-binary-xyz")
    third = await run_shell_command("nonexistent-binary-xyz")

    assert "command not found" in third.lower()
    assert "attempt 3 at this exact command" in third


@pytest.mark.asyncio
async def test_a_zero_threshold_disables_it(monkeypatch):
    monkeypatch.setattr(CFG, "LLM_REPEATED_ATTEMPT_THRESHOLD", 0)

    for _ in range(5):
        result = await run_shell_command("echo off")

    assert "[SYSTEM SUGGESTION]" not in result


@pytest.mark.asyncio
async def test_bash_shares_the_counter():
    """Bash delegates to the shell tool, so the count must not fork."""
    from zrb.llm.tool.bash import run_bash_command

    await run_shell_command("echo shared")
    await run_bash_command("echo shared")
    third = await run_bash_command("echo shared")

    assert "attempt 3 at this exact command" in third


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

    assert "[SYSTEM SUGGESTION]" not in result

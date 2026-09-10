"""Running a task with stdin closed — the shape CI, cron and `< /dev/null` have.

These drive the real `zrb` CLI as a subprocess instead of calling
``prompt_cli_str`` directly, because the bug they pin lives in the gap between
the two. On a closed stdin ``input()`` *raises* ``EOFError``; it never returns
``""``. A unit test that patches ``builtins.input`` therefore asserts a state
that cannot occur, and stays green while the real CLI exits non-zero — which is
exactly what happened before this file existed.

Every case is bounded by a timeout: the first attempt at this fix returned
``""`` from the reader, which fed the empty-answer retry loop in
``BaseInput.prompt_cli_str`` and spun, re-printing the prompt without end. A
hang here is a regression, not a slow machine.
"""

import os
import pathlib
import subprocess
import sys

import pytest

import zrb

# The subprocess gets no pytest.ini, so `pythonpath = ["src"]` does not reach
# it. Point PYTHONPATH at the same tree this test imported zrb from, so the
# child runs the working copy rather than whatever site-packages holds.
_SRC_DIR = str(pathlib.Path(zrb.__file__).resolve().parent.parent)

# Generous enough for a cold interpreter on a loaded CI runner, short enough
# that a spinning prompt fails the suite in seconds rather than wedging it.
_TIMEOUT_SECONDS = 60.0

_ZRB_INIT = """
from zrb import cli, Group, OptionInput, StrInput, make_task

group = cli.add_group(Group(name="ci", description="non-interactive fixtures"))


def _register(name, task_input):
    @make_task(name=name, input=task_input, group=group)
    def _task(ctx):
        ctx.print(f"RESULT[{ctx.input.v}]")


@make_task(name="no-input", group=group)
def _no_input(ctx):
    ctx.print("RESULT[no-input]")


_register("str-default", StrInput("v", default="prod"))
_register("str-empty-ok", StrInput("v", allow_empty=True))
_register("str-required", StrInput("v"))
_register("option-default", OptionInput("v", options=["a", "b"], default="a"))
_register("option-required", OptionInput("v", options=["a", "b"]))
"""


@pytest.fixture
def project(tmp_path: pathlib.Path) -> pathlib.Path:
    """A throwaway project directory holding the fixture task definitions."""
    (tmp_path / "zrb_init.py").write_text(_ZRB_INIT)
    return tmp_path


def _run(
    project: pathlib.Path, *args: str, stdin: str | None = None
) -> subprocess.CompletedProcess:
    """Invoke `zrb <args>` in `project`. `stdin=None` means stdin is closed."""
    env = {**os.environ, "PYTHONPATH": _SRC_DIR}
    try:
        return subprocess.run(
            [sys.executable, "-m", "zrb", *args],
            cwd=project,
            env=env,
            input=stdin,
            stdin=None if stdin is not None else subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:  # pragma: no cover - regression guard
        pytest.fail(
            f"`zrb {' '.join(args)}` did not exit within {_TIMEOUT_SECONDS}s. "
            "A closed stdin must resolve to the default, to empty, or to a "
            "hard error — never to a re-prompt."
        )


@pytest.mark.parametrize(
    "task, expected",
    [
        # A task with no inputs never prompts, so it was never affected.
        ("no-input", "RESULT[no-input]"),
        # The declared default is what the input promises unattended callers.
        ("str-default", "RESULT[prod]"),
        # allow_empty=True says empty is a legitimate answer; EOF is one.
        ("str-empty-ok", "RESULT[]"),
        # OptionInput overrides _prompt_cli_str but inherits prompt_cli_str,
        # so it must be covered by the same handling.
        ("option-default", "RESULT[a]"),
    ],
)
def test_closed_stdin_resolves_to_a_value(project, task, expected):
    result = _run(project, "ci", task)
    assert result.returncode == 0, result.stdout + result.stderr
    assert expected in result.stdout + result.stderr


@pytest.mark.parametrize("task", ["str-required", "option-required"])
def test_closed_stdin_without_a_default_fails_with_the_flag_to_pass(project, task):
    result = _run(project, "ci", task)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    # The message has to say what to do about it, not just that reading failed.
    assert "Cannot read input 'v'" in output
    assert "--v" in output
    # One prompt, not a stream of them: proves the retry loop was not re-entered.
    assert output.count("RESULT[") == 0


def test_closed_stdin_prompts_once_rather_than_spinning(project):
    """The specific regression: a re-prompt loop on an unreadable stdin."""
    result = _run(project, "ci", "str-required")
    output = result.stdout + result.stderr
    assert output.count("Cannot read input") == 1
    assert len(output.splitlines()) < 50, "prompt appears to be repeating"


def test_explicitly_passed_value_wins_over_the_default(project):
    result = _run(project, "ci", "str-default", "--v", "staging")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT[staging]" in result.stdout + result.stderr


def test_piped_stdin_is_still_read(project):
    """Closing stdin is not the same as piping into it; piping must keep working."""
    result = _run(project, "ci", "str-required", stdin="piped\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT[piped]" in result.stdout + result.stderr


def test_piped_blank_lines_still_retry_until_non_empty(project):
    """allow_empty=False keeps rejecting blank answers while stdin has more."""
    result = _run(project, "ci", "str-required", stdin="\n\nfinally\n")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT[finally]" in result.stdout + result.stderr

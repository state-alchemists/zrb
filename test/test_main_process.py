"""`zrb` as a real process: exit codes, signals and output streams.

The rest of the suite drives the engine in-process with mocks, which cannot see
what the shell receives. These run `python -m zrb` against a scratch
`zrb_init.py`.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

posix_only = pytest.mark.skipif(
    not hasattr(os, "killpg"), reason="process groups and SIGTERM are POSIX-only"
)

_INIT = """
from zrb import cli, CmdTask, StrInput, Task

cli.add_task(Task(name="hello", action=lambda ctx: "hi"))
cli.add_task(
    Task(
        name="greet",
        input=StrInput(name="who", prompt="Who"),
        action=lambda ctx: f"hi {ctx.input.who}",
    )
)
cli.add_task(CmdTask(name="fail", cmd="exit 7", retries=0))
# Long enough that it never finishes on its own: a fixed, short sleep here
# races the *test* process's own scheduling under a loaded, contended full
# suite run — if that process is delayed getting around to sending the
# signal, a short sleep can complete naturally first, turning "interrupted"
# tests into false negatives (exit 0 instead of 130/143). Only the signal
# should ever end this.
cli.add_task(CmdTask(name="slow", cmd="echo $$ > child.pid; exec sleep 3600"))
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "zrb_init.py").write_text(_INIT)
    (tmp_path / "home").mkdir()
    return tmp_path


def _env(project: Path, **extra: str) -> dict[str, str]:
    """The child's environment: a real user's shell, not this test run's own.

    `COV_CORE_*` is `pytest-cov`'s own subprocess-coverage hook (see its
    `.pth` file): left in, it makes *this* suite's `--cov=zrb` run start
    coverage tracing inside the spawned `zrb` process too, which perturbs its
    timing and signal handling enough to turn a clean, fast SIGINT/SIGTERM
    exit into a hang or a raw signal kill — only reproducible under a
    coverage-enabled full-suite run, never in isolation.
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("NO_COLOR", "FORCE_COLOR")
        and not key.startswith("ZRB_")
        and not key.startswith("COV_CORE_")
    }
    env.update(HOME=str(project / "home"), ZRB_INIT_SCRIPTS="", **extra)
    return env


def _run(project: Path, *args: str, **extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "zrb", *args],
        cwd=project,
        env=_env(project, **extra),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_result_alone_reaches_stdout(project):
    completed = _run(project, "hello")
    assert completed.returncode == 0
    assert completed.stdout == "hi\n"


def test_a_value_piped_into_a_prompt_leaves_stdout_to_the_result(project):
    completed = subprocess.run(
        [sys.executable, "-m", "zrb", "greet"],
        cwd=project,
        env=_env(project),
        input="bob\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert completed.stdout == "hi bob\n"
    assert "Who: " in completed.stderr


def test_a_failed_command_exits_with_its_own_code(project):
    assert _run(project, "fail").returncode == 7


def test_piped_output_carries_no_escape_codes(project):
    completed = _run(project, "hello")
    assert "\x1b[" not in completed.stderr


def test_no_color_is_honored_even_when_forced(project):
    completed = _run(project, "hello", FORCE_COLOR="1", NO_COLOR="1")
    assert "\x1b[" not in completed.stderr


def test_force_color_styles_piped_output(project):
    assert "\x1b[" in _run(project, "hello", FORCE_COLOR="1").stderr


def _start_slow(project: Path) -> tuple[subprocess.Popen, int]:
    process = subprocess.Popen(
        [sys.executable, "-m", "zrb", "slow"],
        cwd=project,
        env=_env(project),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_file = project / "child.pid"
    deadline = time.monotonic() + 30
    while not (pid_file.exists() and pid_file.read_text().strip()):
        if time.monotonic() > deadline:
            process.kill()
            pytest.fail("the slow command never started")
        time.sleep(0.05)
    return process, int(pid_file.read_text())


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_gone(pid: int, timeout: float = 10) -> bool:
    deadline = time.monotonic() + timeout
    while _is_alive(pid):
        if time.monotonic() > deadline:
            os.kill(pid, signal.SIGKILL)
            return False
        time.sleep(0.05)
    return True


@posix_only
# `zrb`'s own cleanup is quick (`CMD_CLEANUP_TIMEOUT` defaults to 2s), but this
# waits on a real subprocess to be scheduled, signalled and reaped — on a full
# suite run (thousands of other tests forking/execing at the same time) that
# can stretch past a tight budget without a real bug behind it.
def test_ctrl_c_exits_130_and_stops_the_running_command(project):
    process, child = _start_slow(project)
    os.killpg(process.pid, signal.SIGINT)
    assert process.wait(timeout=30) == 130
    assert _wait_gone(child)


@posix_only
def test_sigterm_to_zrb_alone_exits_143_and_stops_the_running_command(project):
    """`docker stop`, systemd and CI cancellation signal only the main PID."""
    process, child = _start_slow(project)
    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=30) == 143
    assert _wait_gone(child)

"""A small, honest evaluation harness for the zrb chat agent.

A task is a fixture workspace, a user request, and checks that read the
workspace afterwards. The agent runs through the real CLI (`zrb llm chat`) in its
own process and its own directory, so what gets measured is the product a user
gets, not an internal API that could drift from it.

Everything here is offline-testable: `run_task` takes a `runner`, and the unit
tests inject one that forges a workspace. Only `test_eval.py` pays for tokens.

Run the suite with `./zrb-test.sh eval`; see `README.md` in this directory.
"""

from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# A check reads the finished workspace and returns a failure reason, or None.
Check = Callable[[Path], "str | None"]

#: Set by `./zrb-test.sh eval`. Without it the suite skips, because each test is
#: a real model call.
RUN_ENV_VAR = "LLM_EVAL_RUN"
#: Optional model override, e.g. `LLM_EVAL_MODEL=deepseek:deepseek-chat`. It has
#: a non-`ZRB_` name on purpose: `test/conftest.py` scrubs the config namespace,
#: so a `ZRB_LLM_MODEL` exported by the developer would not reach this process.
MODEL_ENV_VAR = "LLM_EVAL_MODEL"
DEFAULT_TIMEOUT_SECONDS = 240

_USAGE_RE = re.compile(r"Input: (\d+).*?Output: (\d+)")


def eval_enabled() -> bool:
    """Whether the paid suite was requested (plain falsey values count as off)."""
    return os.environ.get(RUN_ENV_VAR, "").strip().lower() not in (
        "",
        "0",
        "false",
        "off",
        "no",
    )


@dataclass(frozen=True)
class EvalTask:
    """One request, the workspace it starts from, and how to judge the result."""

    name: str
    prompt: str
    files: Mapping[str, str]
    checks: Sequence[Check]
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class CliRun:
    """What one `zrb llm chat` invocation did, independent of how it was launched."""

    exit_code: int
    timed_out: bool
    stdout: str
    stderr: str
    duration_seconds: float


@dataclass
class TaskResult:
    """The verdict on one task, with enough detail to argue with it."""

    name: str
    failures: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    exit_code: int | None = None
    timed_out: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None
    output_tail: str = ""

    @property
    def passed(self) -> bool:
        """A task passes only when the run finished and every check agreed."""
        return not self.failures and not self.timed_out and self.exit_code == 0


def materialize(task: EvalTask, workspace: Path) -> None:
    """Write the task's fixture into *workspace*, creating parent directories."""
    workspace.mkdir(parents=True, exist_ok=True)
    for relative_path, content in task.files.items():
        target = workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def agent_command(prompt: str) -> list[str]:
    """The CLI invocation under test: one turn, no prompts, no approvals."""
    return [
        sys.executable,
        "-m",
        "zrb",
        "llm",
        "chat",
        "--message",
        prompt,
        "--interactive",
        "false",
        "--yolo",
        "true",
    ]


def child_env() -> dict[str, str]:
    """The environment the agent runs with: ours, plus an optional model pick."""
    env = dict(os.environ)
    model = os.environ.get(MODEL_ENV_VAR, "").strip()
    if model:
        env["ZRB_LLM_MODEL"] = model
    return env


def run_cli(task: EvalTask, workspace: Path, timeout: int) -> CliRun:
    """Run the agent once against *workspace* and capture the outcome.

    The child leads its own process group, and a timeout kills that whole group:
    killing only the `zrb` process would leave a shell command it started running,
    free to keep writing into a workspace the harness is already scoring.
    """
    started = time.time()
    process = subprocess.Popen(
        agent_command(task.prompt),
        cwd=str(workspace),
        env=child_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        start_new_session=(os.name != "nt"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        return CliRun(
            exit_code=-1,
            timed_out=True,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_seconds=time.time() - started,
        )
    return CliRun(
        exit_code=process.returncode,
        timed_out=False,
        stdout=stdout or "",
        stderr=stderr or "",
        duration_seconds=time.time() - started,
    )


def kill_process_tree(process: subprocess.Popen) -> None:
    """Kill *process* and anything it spawned. Never raises.

    POSIX: the child is its own group leader, so one `killpg` reaches every
    descendant. The group signalled is the one the OS reports for the child, and
    never this process's own: `run_cli` spawns with `start_new_session`, so a
    match would mean that flag was dropped — and signalling our group would kill
    the test run instead of the agent. Windows has no group signal we can send,
    so `taskkill /T` walks the tree, with `Popen.kill` as the last resort.
    """
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
            )
            return
        except OSError:
            pass
    else:
        try:
            child_group = os.getpgid(process.pid)
        except OSError:
            child_group = None
        if child_group is not None and child_group != os.getpgid(0):
            try:
                os.killpg(child_group, signal.SIGKILL)
                return
            except OSError:
                pass
    try:
        process.kill()
    except OSError:
        pass


def parse_usage(text: str) -> tuple[int | None, int | None]:
    """Pull `Input: N … Output: M` out of the CLI's usage line, when present."""
    match = _USAGE_RE.search(text)
    if match is None:
        return None, None
    return int(match.group(1)), int(match.group(2))


def score(task: EvalTask, workspace: Path, run: CliRun) -> TaskResult:
    """Apply every check to the finished workspace and assemble the verdict."""
    result = TaskResult(name=task.name)
    result.duration_seconds = run.duration_seconds
    result.exit_code = None if run.timed_out else run.exit_code
    result.timed_out = run.timed_out
    result.input_tokens, result.output_tokens = parse_usage(run.stderr)
    result.output_tail = (run.stdout or run.stderr).strip()[-800:]
    if run.timed_out:
        result.failures.append(f"timed out after {run.duration_seconds:.0f}s")
        return result
    for check in task.checks:
        try:
            failure = check(workspace)
        except Exception as error:  # a broken check is a verdict, not a crash
            failure = f"check raised {type(error).__name__}: {error}"
        if failure:
            result.failures.append(failure)
    return result


def run_task(
    task: EvalTask,
    root: Path,
    timeout: int | None = None,
    runner: Callable[[EvalTask, Path, int], CliRun] | None = None,
) -> TaskResult:
    """Materialize, run, and score one task under *root*."""
    workspace = Path(root) / task.name
    materialize(task, workspace)
    effective_timeout = timeout or task.timeout_seconds
    run = (runner or run_cli)(task, workspace, effective_timeout)
    return score(task, workspace, run)


def format_report(results: Sequence[TaskResult]) -> str:
    """A fixed-width summary that can be pasted into a PR or an issue."""
    lines = ["task                          result   time    in/out tokens"]
    for result in results:
        status = "pass" if result.passed else "FAIL"
        tokens = "-"
        if result.input_tokens is not None:
            tokens = f"{result.input_tokens}/{result.output_tokens or 0}"
        lines.append(
            f"{result.name:<29} {status:<8} {result.duration_seconds:>5.0f}s  {tokens}"
        )
        for failure in result.failures:
            lines.append(f"  - {failure}")
    passed = sum(1 for result in results if result.passed)
    lines.append(f"\n{passed}/{len(results)} tasks passed")
    return "\n".join(lines)


# --- helpers the checks use -------------------------------------------------


def read_text(workspace: Path, relative_path: str) -> str:
    """Read a workspace file, or `""` when the agent did not create it."""
    path = workspace / relative_path
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def sha256_text(workspace: Path, relative_path: str) -> str:
    """The file's digest, or `""` when missing, for "this must not change" checks."""
    path = workspace / relative_path
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_python(
    workspace: Path, code: str, timeout: int = 60
) -> tuple[int, str, str]:
    """Run a snippet with the workspace as cwd, so imports resolve like a user's."""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return completed.returncode, completed.stdout, completed.stderr


def run_script(
    workspace: Path, relative_path: str, timeout: int = 60
) -> tuple[int, str, str]:
    """Run a workspace script the way its user would: `python <path>`.

    Prefer this over importing when the request names a script and its output:
    an import skips the `if __name__ == "__main__"` block, so a check built on
    one can pass on code that never produces the output that was asked for.
    """
    completed = subprocess.run(
        [sys.executable, str(workspace / relative_path)],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return completed.returncode, completed.stdout, completed.stderr


def run_pytest(workspace: Path, timeout: int = 120) -> tuple[int, str]:
    """Run the workspace's tests; returns the exit code and a short report."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return completed.returncode, (completed.stdout or "")[-600:]

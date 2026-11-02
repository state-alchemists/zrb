"""Offline tests for the eval harness itself.

These run in the normal suite: they prove the scoring, the fixture writing, and
the reporting behave, so a red `./zrb-test.sh eval` points at the agent rather
than at the harness.
"""

import sys

from harness import (
    CliRun,
    EvalTask,
    format_report,
    materialize,
    parse_usage,
    run_task,
    score,
)
from tasks import TASKS, TASKS_BY_NAME


def _task(**overrides) -> EvalTask:
    fields = {
        "name": "sample",
        "prompt": "do the thing",
        "files": {"a.py": "value = 1\n"},
        "checks": (),
    }
    fields.update(overrides)
    return EvalTask(**fields)


def _run(exit_code=0, timed_out=False, stdout="", stderr="", duration=1.0) -> CliRun:
    return CliRun(
        exit_code=exit_code,
        timed_out=timed_out,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
    )


def test_the_suite_has_fifteen_uniquely_named_tasks():
    assert len(TASKS) == 15
    assert len(TASKS_BY_NAME) == len(TASKS)


def test_every_task_has_at_least_one_check_and_a_prompt():
    for task in TASKS:
        assert task.prompt.strip(), task.name
        assert task.checks, task.name


def test_materialize_writes_nested_fixtures(tmp_path):
    materialize(_task(files={"pkg/mod.py": "x = 1\n"}), tmp_path)
    assert (tmp_path / "pkg" / "mod.py").read_text(encoding="utf-8") == "x = 1\n"


def test_run_task_scores_a_clean_pass(tmp_path):
    def runner(task, workspace, timeout):
        (workspace / "a.py").write_text("value = 2\n", encoding="utf-8")
        return _run()

    task = _task(checks=(lambda workspace: None,))
    result = run_task(task, tmp_path, runner=runner)

    assert result.passed
    assert result.failures == []


def test_a_failing_check_fails_the_task(tmp_path):
    task = _task(checks=(lambda workspace: "value is wrong",))
    result = run_task(task, tmp_path, runner=lambda *args: _run())

    assert not result.passed
    assert result.failures == ["value is wrong"]


def test_a_raising_check_is_a_verdict_not_a_crash(tmp_path):
    def explode(workspace):
        raise RuntimeError("boom")

    result = run_task(_task(checks=(explode,)), tmp_path, runner=lambda *a: _run())

    assert not result.passed
    assert "check raised RuntimeError: boom" in result.failures[0]


def test_a_nonzero_exit_fails_even_when_checks_pass(tmp_path):
    result = run_task(
        _task(checks=(lambda workspace: None,)),
        tmp_path,
        runner=lambda *args: _run(exit_code=1),
    )

    assert not result.passed


def test_a_timeout_fails_with_timeout_detail(tmp_path):
    result = run_task(
        _task(checks=(lambda workspace: None,)),
        tmp_path,
        runner=lambda *args: _run(timed_out=True, exit_code=-1, duration=9.0),
    )

    assert not result.passed
    assert "timed out" in result.failures[0]


def test_parse_usage_reads_the_cli_usage_line():
    assert parse_usage("... Input: 9034 | Output: 12 ...") == (9034, 12)
    assert parse_usage("no usage here") == (None, None)


def test_score_records_usage_from_stderr(tmp_path):
    result = score(
        _task(),
        tmp_path,
        _run(stderr="Input: 100 | Output: 7"),
    )
    assert (result.input_tokens, result.output_tokens) == (100, 7)


def test_report_names_every_task_and_counts_passes(tmp_path):
    passed = run_task(_task(name="one"), tmp_path, runner=lambda *a: _run())
    failed = run_task(
        _task(name="two", checks=(lambda workspace: "nope",)),
        tmp_path,
        runner=lambda *a: _run(),
    )

    report = format_report([passed, failed])

    assert "one" in report and "two" in report
    assert "1/2 tasks passed" in report
    assert "nope" in report


def test_the_cli_command_is_non_interactive_and_self_approving():
    from harness import agent_command

    command = agent_command("hello")
    assert "--interactive" in command and "false" in command
    assert "--yolo" in command and "true" in command


def test_run_python_reports_a_missing_module(tmp_path):
    from harness import run_python

    code, _, err = run_python(tmp_path, "import definitely_not_there")
    assert code != 0
    assert "ModuleNotFoundError" in err


def test_run_pytest_runs_in_the_workspace(tmp_path):
    from harness import run_pytest

    (tmp_path / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    code, _ = run_pytest(tmp_path)
    assert code == 0


def test_run_cli_returns_a_timeout_instead_of_hanging(tmp_path, monkeypatch):
    "The harness must be able to abandon a hung agent rather than hang the suite."
    import harness

    monkeypatch.setattr(
        harness, "agent_command", lambda prompt: [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    run = harness.run_cli(_task(), tmp_path, timeout=1)

    assert run.timed_out
    assert run.exit_code == -1

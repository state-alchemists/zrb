"""Offline tests for the eval harness itself.

These run in the normal suite: they prove the scoring, the fixture writing, and
the reporting behave, so a red `./zrb-test.sh eval` points at the agent rather
than at the harness.
"""

import sys
import time

import pytest
from harness import (
    CliRun,
    EvalTask,
    format_report,
    materialize,
    parse_usage,
    run_task,
    score,
)
from tasks import BROKEN_FIXTURE, FAILING_TEST_IN_LOG, TASKS, TASKS_BY_NAME

from zrb.config.config import CFG
from zrb.llm.config.limiter import LLMLimiter


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


def test_the_suite_has_sixteen_uniquely_named_tasks():
    assert len(TASKS) == 16
    assert len(TASKS_BY_NAME) == len(TASKS)


def test_the_large_log_fixture_stays_over_the_prune_budget():
    """The big-output task must stay too big to arrive whole.

    The numbers come from the live config and from the pruner itself, not from
    literals: a threshold raised by one environment variable would otherwise
    leave the log arriving intact while this test stayed green. Until per-result
    pruning exists on this tree (`#811`), the premise cannot hold, so the test
    says so instead of certifying it.
    """
    pruner = pytest.importorskip(
        "zrb.llm.summarizer.tool_result_pruner",
        reason="per-result pruning lands with #811; until then the log arrives whole",
    )
    log = TASKS_BY_NAME["find_in_large_log"].files["logs/build.log"]
    limiter = LLMLimiter()
    budget = CFG.LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD
    tokens = limiter.count_tokens(log)
    assert tokens > budget, (
        f"the log is {tokens} tokens against a {budget}-token prune budget, so "
        "nothing is pruned and the task measures nothing about oversized output. "
        "Lower ZRB_LLM_MESSAGE_SUMMARIZATION_TOKEN_THRESHOLD, or lengthen the "
        "fixture past the budget this machine actually runs with."
    )
    before_answer = log[: log.index(FAILING_TEST_IN_LOG)]
    kept_head = pruner.HEAD_SHARE * budget
    assert limiter.count_tokens(before_answer) > kept_head, (
        "the answer sits inside the head the pruner keeps, so an agent that "
        "reads the result without searching still finds it"
    )


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


# --- the checks must reject a plausible wrong answer -------------------------


def _broken(fix: str) -> str:
    return BROKEN_FIXTURE.replace("    return total + missing_offset", fix)


def test_fix_runtime_error_check_rejects_a_wrong_constant(tmp_path):
    "Defining the missing name as 0 makes the script run but print 6, not 42."
    (tmp_path / "broken.py").write_text(
        "missing_offset = 0\n" + _broken("    return total + missing_offset"),
        encoding="utf-8",
    )

    failure = TASKS_BY_NAME["fix_runtime_error"].checks[0](tmp_path)

    assert failure is not None
    assert "42" in failure


def test_fix_runtime_error_check_rejects_a_hardcoded_print(tmp_path):
    "Printing 42 directly must not pass: the loop is gone, the name never used."
    (tmp_path / "broken.py").write_text(
        'if __name__ == "__main__":\n    print(42)\n', encoding="utf-8"
    )

    assert TASKS_BY_NAME["fix_runtime_error"].checks[0](tmp_path) is not None


def test_fix_runtime_error_check_accepts_the_intended_fix(tmp_path):
    (tmp_path / "broken.py").write_text(
        "missing_offset = 36\n" + _broken("    return total + missing_offset"),
        encoding="utf-8",
    )

    assert TASKS_BY_NAME["fix_runtime_error"].checks[0](tmp_path) is None


def test_refactor_check_rejects_an_unused_helper(tmp_path):
    "A normalize() that nothing calls leaves the duplication the task named."
    (tmp_path / "report_text.py").write_text(
        "def normalize(text):\n"
        '    return " ".join(text.strip().split())\n'
        "\n"
        "\n"
        "def header(title):\n"
        '    return " ".join(title.strip().split()).upper()\n'
        "\n"
        "\n"
        "def footer(text):\n"
        '    return " ".join(text.strip().split()).lower()\n',
        encoding="utf-8",
    )

    failure = TASKS_BY_NAME["refactor_extract"].checks[0](tmp_path)

    assert failure is not None
    assert "not used" in failure


def test_add_test_check_rejects_tests_that_do_not_exercise_the_function(tmp_path):
    (tmp_path / "slugify.py").write_text(
        'def slugify(text):\n    return "-".join(text.lower().split())\n',
        encoding="utf-8",
    )
    (tmp_path / "test_slugify.py").write_text(
        "def test_one():\n    assert True\n\n\ndef test_two():\n    assert 1\n",
        encoding="utf-8",
    )

    failure = TASKS_BY_NAME["add_test_for_function"].checks[0](tmp_path)

    assert failure is not None
    assert "slugify" in failure


def test_a_timeout_kills_the_agent_and_its_grandchildren(tmp_path, monkeypatch):
    "A tool command that outlives the timeout must not keep writing to the fixture."
    import harness

    late_write = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', "
        "\"import time; time.sleep(3); open('late.txt','w').write('x')\"])\n"
        "time.sleep(60)\n"
    )
    monkeypatch.setattr(
        harness,
        "agent_command",
        lambda prompt: [sys.executable, "-c", late_write],
    )

    run = harness.run_cli(_task(), tmp_path, timeout=1)

    assert run.timed_out
    # The grandchild sleeps 3s; if it survived the group kill it writes here.
    time.sleep(4)
    assert not (tmp_path / "late.txt").exists()

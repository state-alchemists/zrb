import sys

import pytest

from zrb.__main__ import serve_cli

FAILING_INIT = """
from zrb import cli, Group, Task

group = cli.add_group(Group("{group}"))
group.add_task(Task(name="boom", action=lambda ctx: 1 / 0, retries=0))
"""


def _run_failing_task(tmp_path, monkeypatch, group: str) -> str:
    init = tmp_path / "zrb_init.py"
    init.write_text(FAILING_INIT.format(group=group))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb", group, "boom"])
    with pytest.raises(SystemExit):
        serve_cli()
    return group


def test_a_failed_task_points_at_the_env_var_that_reveals_the_traceback(
    tmp_path, capsys, monkeypatch
):
    """The default failure line is just `<Type>: <message>` — no file, no line.
    The traceback exists behind DEBUG, so the failure has to name the way in;
    otherwise the escape hatch only helps people who already knew about it."""
    _run_failing_task(tmp_path, monkeypatch, "hintcheck")
    captured = capsys.readouterr()
    assert "ZeroDivisionError: division by zero" in captured.err
    assert "ZRB_LOGGING_LEVEL=DEBUG" in captured.err


def test_the_traceback_hint_honors_a_white_labeled_env_prefix(
    tmp_path, capsys, monkeypatch
):
    """A distribution that rebrands via `_ZRB_ENV_PREFIX` reads
    `ACME_LOGGING_LEVEL`, so printing a hardcoded `ZRB_`-prefixed name would
    hand its users a variable that does nothing. See
    `docs/advanced-topics/white-labeling.md`."""
    monkeypatch.setenv("_ZRB_ENV_PREFIX", "ACME")
    _run_failing_task(tmp_path, monkeypatch, "hintcheck-white-label")
    captured = capsys.readouterr()
    assert "ACME_LOGGING_LEVEL=DEBUG" in captured.err
    assert "ZRB_LOGGING_LEVEL" not in captured.err


def test_a_broken_init_script_reports_file_line_and_type_but_still_runs(
    tmp_path, capsys, monkeypatch
):
    """A broken `zrb_init.py` is never hidden, but it is not fatal: the CLI
    still starts with whatever partial state resulted, since a user who can
    see the error and still run zrb can fix it and rerun."""
    broken = tmp_path / "zrb_init.py"
    broken.write_text("this_name_does_not_exist()\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    serve_cli()  # does not raise SystemExit — the CLI still runs
    captured = capsys.readouterr()
    assert "zrb_init.py" in captured.err
    assert "NameError" in captured.err
    # cli.run([]) with no subcommand prints the group/task listing to stdout —
    # proof startup actually continued past the broken init script.
    assert "GROUPS" in captured.out


PARTIAL_INIT = """
from zrb import cli, Task

cli.add_task(
    Task(name="{task}", action=lambda ctx: open({sentinel!r}, "w").write("ran"))
)
raise RuntimeError("init failed after registering the task")
"""

ABORT_MESSAGE = "_INIT_STRICT is on"


def test_strict_init_is_off_by_default_so_a_partial_init_still_runs_the_task(
    tmp_path, capsys, monkeypatch
):
    """With INIT_STRICT off, a failed init source is reported and startup
    continues, so a task registered before the failure still runs."""
    sentinel = tmp_path / "ran.txt"
    init = tmp_path / "zrb_init.py"
    init.write_text(PARTIAL_INIT.format(task="default-partial", sentinel=str(sentinel)))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb", "default-partial"])
    serve_cli()  # no SystemExit
    captured = capsys.readouterr()
    assert "RuntimeError: init failed after registering the task" in captured.err
    assert ABORT_MESSAGE not in captured.err
    assert sentinel.exists()


def test_strict_init_aborts_before_running_the_task(tmp_path, capsys, monkeypatch):
    """With INIT_STRICT on, a failed init source aborts startup before the CLI
    runs. The sentinel the task would have written proves it never ran."""
    sentinel = tmp_path / "ran.txt"
    init = tmp_path / "zrb_init.py"
    init.write_text(PARTIAL_INIT.format(task="strict-partial", sentinel=str(sentinel)))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZRB_INIT_STRICT", "true")
    monkeypatch.setattr(sys, "argv", ["zrb", "strict-partial"])
    with pytest.raises(SystemExit) as exc_info:
        serve_cli()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "RuntimeError: init failed after registering the task" in captured.err
    assert f"ZRB{ABORT_MESSAGE}" in captured.err
    assert not sentinel.exists()


def test_strict_init_does_not_abort_when_every_init_source_loads(
    tmp_path, capsys, monkeypatch
):
    """Strict mode aborts on a failed init source, not on being enabled: a
    clean init runs the task as it would with the flag off."""
    sentinel = tmp_path / "ran.txt"
    init = tmp_path / "zrb_init.py"
    init.write_text(
        "from zrb import cli, Task\n"
        "cli.add_task(Task(name='strict-clean', "
        f"action=lambda ctx: open({str(sentinel)!r}, 'w').write('ran')))\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZRB_INIT_STRICT", "true")
    monkeypatch.setattr(sys, "argv", ["zrb", "strict-clean"])
    serve_cli()  # no SystemExit
    assert ABORT_MESSAGE not in capsys.readouterr().err
    assert sentinel.exists()


def test_strict_init_abort_message_honors_a_white_labeled_env_prefix(
    tmp_path, capsys, monkeypatch
):
    """A distribution that rebrands via `_ZRB_ENV_PREFIX` reads
    `ACME_INIT_STRICT`, so the abort message must name that prefix.
    See `docs/advanced-topics/white-labeling.md`."""
    init = tmp_path / "zrb_init.py"
    init.write_text("this_name_does_not_exist()\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("_ZRB_ENV_PREFIX", "ACME")
    monkeypatch.setenv("ACME_INIT_STRICT", "true")
    monkeypatch.setattr(sys, "argv", ["zrb"])
    with pytest.raises(SystemExit):
        serve_cli()
    assert f"ACME{ABORT_MESSAGE}" in capsys.readouterr().err

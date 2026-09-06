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

import sys

import pytest

from zrb.__main__ import serve_cli
from zrb.config.config import CFG

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


CLAIM_INIT = """
from zrb import cli, Task
from zrb.config.config import CFG

CFG.PROJECT_ENV_KEYS = ["LLM_PLUGIN_DIR"]


def claim_ok(ctx):
    return None


cli.add_task(Task(name="claimcheck", action=claim_ok))
"""


def test_a_typo_warning_names_a_projects_unclaimed_variable(
    tmp_path, capsys, monkeypatch
):
    """The warning is real and reachable — without this, the claim test below
    would pass for the wrong reason."""
    monkeypatch.setenv("ZRB_LLM_PLUGIN_DIR", "/opt/zrb-plugins")
    init = tmp_path / "zrb_init.py"
    init.write_text("from zrb import cli\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    serve_cli()
    captured = capsys.readouterr()
    assert "ZRB_LLM_PLUGIN_DIR" in captured.err
    assert "is not a setting" in captured.err


def test_a_claim_from_an_init_source_silences_the_typo_warning(
    tmp_path, capsys, monkeypatch
):
    """`_warn_mistyped_env_keys` runs after the init sources load, which is
    what lets a distribution claim its own variables from `zrb_init.py`. The
    ordering is the feature, so it is pinned here: moving the warning ahead
    of the sources would break every white label that uses it."""
    monkeypatch.setenv("ZRB_LLM_PLUGIN_DIR", "/opt/zrb-plugins")
    monkeypatch.delenv("ZRB_PROJECT_ENV_KEYS", raising=False)
    init = tmp_path / "zrb_init.py"
    init.write_text(CLAIM_INIT)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    serve_cli()
    assert "ZRB_LLM_PLUGIN_DIR" not in capsys.readouterr().err


def test_a_broken_init_script_reports_file_line_and_type_but_still_runs(
    tmp_path, capsys, monkeypatch
):
    """A broken `zrb_init.py` is never hidden, and at an interactive terminal
    it is not fatal: the CLI still starts with whatever partial state
    resulted, since a user who can see the error and still run zrb can fix it
    and rerun. Pinned with `INIT_STRICT` off explicitly — under pytest stderr
    is captured, which `auto` reads as "nobody is watching"."""
    monkeypatch.setenv("ZRB_INIT_STRICT", "off")
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


def test_strict_init_off_lets_a_partial_init_still_run_the_task(
    tmp_path, capsys, monkeypatch
):
    """With INIT_STRICT off, a failed init source is reported and startup
    continues, so a task registered before the failure still runs."""
    monkeypatch.setenv("ZRB_INIT_STRICT", "off")
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


class _FakeStderr:
    """Minimal stderr stand-in — `CFG.INIT_STRICT` only asks it `isatty()`."""

    def __init__(self, tty: bool):
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


@pytest.mark.parametrize(
    "tty, expected",
    [(True, False), (False, True)],
    ids=["terminal-is-lenient", "pipe-is-strict"],
)
def test_strict_init_auto_follows_whether_stderr_is_a_terminal(
    monkeypatch, tty, expected
):
    """`auto` is the default, and resolves against stderr on every read.

    The case for continuing past a broken init source is that the user reads
    the error and reruns. Where stderr is not a terminal — CI, a cron job, a
    piped run — nobody reads it, and the run otherwise exits 0 against
    configuration that was never finished.
    """
    monkeypatch.delenv("ZRB_INIT_STRICT", raising=False)
    monkeypatch.setattr(sys, "stderr", _FakeStderr(tty))
    assert CFG.INIT_STRICT is expected


def test_strict_init_auto_can_be_requested_explicitly(monkeypatch):
    """`ZRB_INIT_STRICT=auto` is the written form of the default, so a shell
    profile can set it back after a CI job forced it on."""
    monkeypatch.setenv("ZRB_INIT_STRICT", "auto")
    monkeypatch.setattr(sys, "stderr", _FakeStderr(True))
    assert CFG.INIT_STRICT is False


def test_an_unregistered_task_in_init_is_named_at_startup(
    tmp_path, capsys, monkeypatch
):
    """A task declared in `zrb_init.py` but never registered is a live object
    with a name and no CLI word. Startup names it rather than letting
    `zrb <name>` fall through to the "did you mean" listing."""
    init = tmp_path / "zrb_init.py"
    init.write_text(
        "from zrb import CmdTask\n"
        "orphan = CmdTask(name='detached-orphan', cmd='echo hi', retries=0)\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    serve_cli()
    captured = capsys.readouterr()
    assert "detached-orphan" in captured.err
    assert "not registered" in captured.err


def test_a_task_declared_before_a_failing_init_line_is_still_named(
    tmp_path, capsys, monkeypatch
):
    """Declarations before a failing line are already live in the CLI tree, so
    the diagnostics must see the partially executed module, not lose it with
    the error that ended the source."""
    monkeypatch.setenv("ZRB_INIT_STRICT", "off")
    init = tmp_path / "zrb_init.py"
    init.write_text(
        "from zrb import CmdTask\n"
        "orphan = CmdTask(name='declared-before-failure', cmd='echo hi', retries=0)\n"
        "raise RuntimeError('init failed after declaring the task')\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])
    serve_cli()
    captured = capsys.readouterr()
    assert "RuntimeError: init failed after declaring the task" in captured.err
    assert "declared-before-failure" in captured.err
    assert "not registered" in captured.err


def test_a_project_task_from_an_earlier_run_is_not_treated_as_a_builtin(
    tmp_path, capsys, monkeypatch
):
    """`cli` outlives a run. A task an earlier run registered must not be
    frozen into the built-in set, or replacing it on the next run would be
    silenced as an intended shadow instead of warned as a collision."""
    init = tmp_path / "zrb_init.py"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["zrb"])

    init.write_text(
        "from zrb import CmdTask, cli\n"
        "first = CmdTask(name='repeat-run-task', cmd='echo one', retries=0)\n"
        "cli.add_task(first)\n"
    )
    serve_cli()
    capsys.readouterr()

    init.write_text(
        "from zrb import CmdTask, cli\n"
        "second = CmdTask(name='repeat-run-task', cmd='echo two', retries=0)\n"
        "cli.add_task(second)\n"
    )
    serve_cli()
    captured = capsys.readouterr()
    assert "repeat-run-task" in captured.err
    assert "more than one task" in captured.err


def test_a_mistyped_setting_variable_is_named_with_the_setting_it_meant(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("ZRB_LLM_MODELL", "openai:gpt-4o")
    _run_failing_task(tmp_path, monkeypatch, "typocheck")
    captured = capsys.readouterr()
    assert (
        "ZRB_LLM_MODELL is not a setting and is ignored. Did you mean ZRB_LLM_MODEL?"
        in captured.err
    )


def test_a_retired_setting_variable_is_named_with_its_replacement(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("ZRB_LLM_UI_COMMAND_PHOTO", "/snap")
    _run_failing_task(tmp_path, monkeypatch, "retiredcheck")
    captured = capsys.readouterr()
    assert (
        "ZRB_LLM_UI_COMMAND_PHOTO is no longer read and is ignored. "
        "Set ZRB_LLM_CAMERA_COMMANDS instead." in captured.err
    )


def test_a_retired_setting_with_no_replacement_is_named_with_why(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("ZRB_LLM_VOICE_ENABLED", "on")
    _run_failing_task(tmp_path, monkeypatch, "retiredwhy")
    captured = capsys.readouterr()
    assert (
        "ZRB_LLM_VOICE_ENABLED is no longer read and is ignored: "
        "/voice is always offered." in captured.err
    )

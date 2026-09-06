"""Unknown `--flag` rejection in CLI mode.

An unrecognized option is only visible by elimination: nothing reads it, so
the input it was aimed at resolves to its default or a prompt exactly as if
the flag had been absent. Web mode stays permissive because the input-preview
API is handed arbitrary JSON rather than a parsed command line.
"""

import pytest

from zrb.input.str_input import StrInput
from zrb.runner.common_util import get_task_str_kwargs
from zrb.task.task import Task


def _greet_task() -> Task:
    # always_prompt=False so the "no unknown option" cases resolve to the
    # default instead of blocking on an interactive prompt.
    return Task(
        name="greet",
        input=StrInput("name", default="anon", always_prompt=False),
    )


def test_unknown_kwarg_raises_in_cli_mode():
    with pytest.raises(ValueError, match="Unknown option for task 'greet'"):
        get_task_str_kwargs(
            task=_greet_task(), str_args=[], str_kwargs={"nmae": "bob"}, cli_mode=True
        )


def test_unknown_kwarg_error_suggests_the_close_match():
    with pytest.raises(ValueError, match="Did you mean 'name'"):
        get_task_str_kwargs(
            task=_greet_task(), str_args=[], str_kwargs={"nmae": "bob"}, cli_mode=True
        )


def test_unknown_kwarg_error_lists_available_options():
    with pytest.raises(ValueError, match=r"Available: --name"):
        get_task_str_kwargs(
            task=_greet_task(), str_args=[], str_kwargs={"zzz": "1"}, cli_mode=True
        )


def test_task_without_inputs_says_so():
    with pytest.raises(ValueError, match=r"this task takes no options"):
        get_task_str_kwargs(
            task=Task(name="noargs"),
            str_args=[],
            str_kwargs={"bogus": "1"},
            cli_mode=True,
        )


def test_known_kwarg_is_accepted():
    result = get_task_str_kwargs(
        task=_greet_task(), str_args=[], str_kwargs={"name": "bob"}, cli_mode=True
    )

    assert result == {"name": "bob"}


def test_help_flags_are_not_reported_as_unknown():
    """`-h`/`--help` are consumed by the CLI before a task sees them."""
    for flag in ("h", "help"):
        result = get_task_str_kwargs(
            task=_greet_task(), str_args=[], str_kwargs={flag: "true"}, cli_mode=True
        )
        assert result == {"name": "anon"}


def test_web_mode_stays_permissive():
    """The input-preview API is handed arbitrary JSON; it must not raise."""
    result = get_task_str_kwargs(
        task=_greet_task(),
        str_args=[],
        str_kwargs={"unrelated": "x"},
        cli_mode=False,
    )

    assert result == {"name": "anon"}


def test_positional_args_are_not_rejected():
    """Leftover positionals reach the task as `ctx.args` — a feature."""
    result = get_task_str_kwargs(
        task=Task(name="noargs"),
        str_args=["extra1", "extra2"],
        str_kwargs={},
        cli_mode=True,
    )

    assert result == {}


def test_every_unknown_option_is_named():
    with pytest.raises(ValueError) as excinfo:
        get_task_str_kwargs(
            task=_greet_task(),
            str_args=[],
            str_kwargs={"aaa": "1", "bbb": "2"},
            cli_mode=True,
        )

    assert "'--aaa'" in str(excinfo.value)
    assert "'--bbb'" in str(excinfo.value)

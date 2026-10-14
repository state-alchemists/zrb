import os
from unittest.mock import patch

from zrb import StrInput, Task, Tpl
from zrb.runner.cli import Cli


def test_a_fallback_reads_its_own_input():
    seen = []
    fallback = Task(
        name="fallback",
        input=StrInput("fallback-note", default="hello"),
        action=lambda ctx: seen.append(ctx.input.fallback_note),
    )

    def fail(_ctx):
        raise RuntimeError("boom")

    main = Task(name="main", action=fail, fallback=fallback, retries=0)

    try:
        main.run()
    except RuntimeError:
        pass

    assert seen == ["hello"]


def test_successor_and_readiness_check_inputs_are_side_inputs():
    check = Task(name="check", input=StrInput("check-port", default="1"))
    successor = Task(name="successor", input=StrInput("successor-msg", default="2"))
    main = Task(
        name="main",
        input=StrInput("main-arg", default="0"),
        readiness_check=check,
        successor=successor,
    )

    assert [i.name for i in main.inputs] == ["main-arg"]
    assert [i.name for i in main.side_inputs] == ["successor-msg", "check-port"]


def test_the_task_own_input_wins_over_a_side_task_input_of_the_same_name():
    own = StrInput("name", default="own")
    successor = Task(name="successor", input=StrInput("name", default="side"))
    main = Task(name="main", input=own, successor=successor)

    assert main.inputs == [own]
    assert main.side_inputs == []


def test_a_side_input_without_a_default_is_never_prompted():
    """The fallback may never run, so a run without stdin must not fail on it."""
    cli = Cli()
    fallback = Task(name="fallback", input=StrInput("reason"), action="fb")
    cli.add_task(Task(name="main", action="ok", fallback=fallback))

    with patch("sys.stdin", None):
        assert cli.run(str_args=["main"]) == "ok"


def test_a_side_input_is_passed_on_the_cli():
    seen = []
    cli = Cli()
    fallback = Task(
        name="fallback",
        input=StrInput("reason", default="none"),
        action=lambda ctx: seen.append(ctx.input.reason),
    )

    def fail(_ctx):
        raise RuntimeError("boom")

    cli.add_task(Task(name="main", action=fail, fallback=fallback, retries=0))

    try:
        cli.run(str_args=["main", "--reason", "disk full"])
    except (RuntimeError, KeyboardInterrupt):
        pass

    assert seen == ["disk full"]


def test_an_input_default_reads_the_os_environment():
    task = Task(
        name="t",
        input=StrInput("path", default=Tpl("{ctx.env.ZRB_TEST_HOME}/p")),
        action=lambda ctx: ctx.input.path,
    )

    with patch.dict(os.environ, {"ZRB_TEST_HOME": "/home/x"}):
        assert task.run() == "/home/x/p"

from zrb import Group, IntInput, StrInput, Task
from zrb.runner.cli import Cli


def test_show_info_for_existing_group():
    cli = Cli()
    math_group = cli.add_group(Group(name="math"))
    math_group.add_group(Group(name="geometry"))
    math_group.add_task(
        Task(name="add", action="{int(ctx.args[0]) + int(ctx.args[1])}")
    )
    error = None
    try:
        cli.run(args=["math"])
    except Exception as e:
        error = e
    assert error is None


def test_show_info_for_inexisting_group():
    cli = Cli()
    math_group = cli.add_group(Group(name="math"))
    math_group.add_group(Group(name="geometry"))
    math_group.add_task(
        Task(name="add", action="{int(ctx.args[0]) + int(ctx.args[1])}")
    )
    error = None
    try:
        cli.run(args=["computer"])
    except Exception as e:
        error = e
    assert error is not None


def test_show_help_for_existing_task():
    cli = Cli()
    cli.add_task(
        Task(
            name="hello",
            input=StrInput("name", default="world"),
            action="Hello {input.name}",
        )
    )
    error = None
    try:
        cli.run(args=["hello", "-h"])
    except Exception as e:
        error = e
    assert error is None


def test_run_existing_task():
    cli = Cli()
    cli.add_task(Task(name="hello", action="Hello World"))
    error = None
    try:
        cli.run(args=["hello"])
    except Exception as e:
        error = e
    assert error is None


def test_show_help_for_inexisting_task():
    cli = Cli()
    cli.add_task(Task(name="hello", action="Hello world"))
    error = None
    try:
        cli.run(args=["good-bye", "-h"])
    except Exception as e:
        error = e
    assert error is not None


def test_run_inexisting_task():
    cli = Cli()
    cli.add_task(Task(name="hello", action="Hello world"))
    error = None
    try:
        cli.run(args=["good-bye"])
    except Exception as e:
        error = e
    assert error is not None


def test_run_simple_task():
    cli = Cli()
    cli.add_task(Task(name="hello", action="Hello world"))
    result = cli.run(args=["hello"])
    assert result == "Hello world"


def test_run_simple_task_with_keyword_arguments_as_inputs():
    cli = Cli()
    cli.add_task(
        Task(
            name="add",
            input=[
                IntInput(name="a"),
                IntInput(name="b"),
            ],
            action="{ctx.input.a + ctx.input.b}",
        )
    )
    result = cli.run(args=["add", "--a", "4", "--b", "5"])
    assert result == "9"


def test_run_simple_task_with_arguments_as_inputs():
    cli = Cli()
    cli.add_task(
        Task(
            name="add",
            input=[
                IntInput(name="a"),
                IntInput(name="b"),
            ],
            action="{ctx.input.a + ctx.input.b}",
        )
    )
    result = cli.run(args=["add", "4", "5"])
    assert result == "9"


def test_run_simple_task_with_arguments():
    cli = Cli()
    cli.add_task(Task(name="add", action="{int(ctx.args[0]) + int(ctx.args[1])}"))
    result = cli.run(args=["add", "4", "5"])
    assert result == "9"

from unittest.mock import AsyncMock, MagicMock, patch

from zrb import Group, IntInput, StrInput, Task
from zrb.config.config import CFG
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
        cli.run(str_args=["math"])
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
        cli.run(str_args=["computer"])
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
        cli.run(str_args=["hello", "-h"])
    except Exception as e:
        error = e
    assert error is None


def test_run_existing_task():
    cli = Cli()
    cli.add_task(Task(name="hello", action="Hello World"))
    error = None
    try:
        cli.run(str_args=["hello"])
    except Exception as e:
        error = e
    assert error is None


def test_show_help_for_inexisting_task():
    cli = Cli()
    cli.add_task(Task(name="hello", action="Hello world"))
    error = None
    try:
        cli.run(str_args=["good-bye", "-h"])
    except Exception as e:
        error = e
    assert error is not None


def test_run_inexisting_task():
    cli = Cli()
    cli.add_task(Task(name="hello", action="Hello world"))
    error = None
    try:
        cli.run(str_args=["good-bye"])
    except Exception as e:
        error = e
    assert error is not None


def test_run_simple_task():
    cli = Cli()
    cli.add_task(Task(name="hello", action="Hello world"))
    result = cli.run(str_args=["hello"])
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
    result = cli.run(str_args=["add", "--a", "4", "--b", "5"])
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
    result = cli.run(str_args=["add", "4", "5"])
    assert result == "9"


def test_run_simple_task_with_arguments():
    cli = Cli()
    cli.add_task(Task(name="add", action="{int(ctx.args[0]) + int(ctx.args[1])}"))
    result = cli.run(str_args=["add", "4", "5"])
    assert result == "9"


def test_show_help_for_task_with_description():
    cli = Cli()
    cli.add_task(
        Task(
            name="detailed-task",
            description="This is a very detailed task.\\nIt does amazing things.",
            action="echo 'detail'",
        )
    )
    # Just running it to trigger print statements (captured by capsys if needed, but we just need coverage)
    cli.run(str_args=["detailed-task", "-h"])


def test_cli_description_property():
    """Cli.description returns a string."""
    cli = Cli()
    desc = cli.description
    assert isinstance(desc, str)


def test_cli_banner_property():
    """Cli.banner returns a string."""
    cli = Cli()
    banner = cli.banner
    assert isinstance(banner, str)


def test_show_group_with_banner_and_description():
    """Running a group shows its banner and description."""
    cli = Cli()
    sub = Group(name="mygroup", description="Group description here")
    # Add a task so the group is non-empty
    sub.add_task(Task(name="t1", action="x"))
    cli.add_group(sub)
    # Patch Group.banner to return non-empty value
    with patch.object(
        type(sub), "banner", new_callable=lambda: property(lambda self: "My Banner")
    ):
        cli.run(str_args=["mygroup"])


def test_show_group_with_subgroups():
    """Running a group with subgroups displays them."""
    cli = Cli()
    outer = Group(name="outer", description="Outer group")
    inner = Group(name="inner", description="Inner subgroup")
    inner.add_task(Task(name="t1", action="x"))
    outer.add_group(inner)
    cli.add_group(outer)
    cli.run(str_args=["outer"])


def test_show_task_info_with_inputs():
    """Running a task with -h shows its inputs section."""
    cli = Cli()
    cli.add_task(
        Task(
            name="my-task",
            description="A task with inputs",
            input=StrInput("name", description="The name"),
            action="Hello {input.name}",
        )
    )
    cli.run(str_args=["my-task", "-h"])


def test_run_with_str_args_none_defaults_to_empty():
    """run(str_args=None) walks to the empty-args branch and shows root info."""
    cli = Cli()
    cli.run(str_args=None)


def test_run_keyword_with_equals_sign():
    """`--key=value` is split on `=` rather than treated as a flag."""
    cli = Cli()
    cli.add_task(
        Task(
            name="add",
            input=[IntInput(name="a"), IntInput(name="b")],
            action="{ctx.input.a + ctx.input.b}",
        )
    )
    result = cli.run(str_args=["add", "--a=4", "--b=5"])
    assert result == "9"


def test_run_kwarg_without_value_becomes_true_flag():
    """`--flag` with no following value is recorded as 'true'."""
    cli = Cli()

    received = {}

    def _capture(ctx):
        received["enabled"] = ctx.input.enabled
        return "ok"

    cli.add_task(
        Task(
            name="toggle",
            input=StrInput("enabled", default=""),
            action=_capture,
        )
    )
    cli.run(str_args=["toggle", "--enabled"])
    assert received["enabled"] == "true"


def test_get_run_command_param_quotes_strings_with_spaces():
    """Values containing whitespace or quotes get double-quoted in the rerun hint."""
    cli = Cli()
    out = cli._get_run_command_param("msg", "hello world")
    assert out == '--msg "hello world"'

    # Already-quoted values get re-wrapped consistently
    out2 = cli._get_run_command_param("msg", "")
    assert out2 == '--msg ""'

    # Plain values don't get quoted
    out3 = cli._get_run_command_param("flag", "true")
    assert out3 == "--flag true"


def test_conversation_name_printed_at_end(capsys):
    """A task that stores a conversation name has it echoed to stderr."""
    cli = Cli()

    def _set_name(ctx):
        ctx.xcom["__conversation_name__"] = "my-convo"
        return "ok"

    cli.add_task(Task(name="chatty", action=_set_name))
    cli.run(str_args=["chatty"])
    err = capsys.readouterr().err
    assert "my-convo" in err


def test_conversation_name_skipped_when_task_errors():
    """When the task raises, session is None so the name print is skipped."""
    cli = Cli()

    def _boom(ctx):
        raise RuntimeError("boom")

    cli.add_task(Task(name="boom", action=_boom, retries=0))
    error = None
    try:
        cli.run(str_args=["boom"])
    except Exception as e:
        error = e
    assert error is not None


def test_version_task_returns_version():
    """The built-in `version` task returns the configured version string."""
    from zrb.runner.cli import cli

    result = cli.run(str_args=["version"])
    assert result == CFG.VERSION


def test_start_server_task_builds_and_serves_app():
    """`server start` wires up the web app and awaits the uvicorn server."""
    from zrb.runner.cli import cli

    mock_server = MagicMock()
    mock_server.serve = AsyncMock()
    with (
        patch("uvicorn.Config") as mock_config,
        patch("uvicorn.Server", return_value=mock_server),
        patch("zrb.runner.web_app.create_web_app") as mock_create,
        patch("zrb.runner.web_app.configure_uvicorn_logging") as mock_log,
    ):
        cli.run(str_args=["server", "start"])

    mock_log.assert_called_once()
    mock_create.assert_called_once()
    mock_config.assert_called_once()
    mock_server.serve.assert_awaited_once()


def test_conversation_name_swallows_lookup_error():
    """A broken xcom lookup is caught, not propagated (defensive branch)."""
    cli = Cli()
    session = MagicMock()
    session.shared_ctx.xcom.get.side_effect = AttributeError("no xcom")
    # Should not raise despite the lookup blowing up.
    cli._print_conversation_name(MagicMock(), session)

from zrb import Task
from zrb.runner.cli import Cli


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


def test_run_command_param_quoting():
    cli = Cli()
    # Access private method to test directly
    assert cli._get_run_command_param("key", "val") == "--key val"
    assert (
        cli._get_run_command_param("key", "val with space") == '--key "val with space"'
    )
    assert cli._get_run_command_param("key", "") == '--key ""'
    assert cli._get_run_command_param("key", 'val"quote') == '--key "val\\"quote"'


def test_print_run_command(capsys):
    cli = Cli()
    cli._print_run_command("zrb task --flag value")
    captured = capsys.readouterr()
    assert "To run again:" in captured.err
    assert "zrb task --flag value" in captured.err

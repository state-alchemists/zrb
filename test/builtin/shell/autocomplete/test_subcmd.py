from unittest.mock import MagicMock, patch

from zrb.builtin.shell.autocomplete.subcmd import get_shell_subcommands


def _action(task):
    """`task.action` narrowed to the callable `@make_task` always sets."""
    action = task.action
    assert callable(action)
    return action


def test_get_shell_subcommands_logic():
    ctx = MagicMock()
    ctx.args = ["zrb", "test"]

    # Mock return value of get_group_subcommands
    from zrb.util.cli.subcommand import SubCommand

    mock_subcommands = [
        SubCommand(paths=["zrb", "test"], nexts=["cmd1", "cmd2"]),
        SubCommand(paths=["zrb", "other"], nexts=["cmd3"]),
    ]

    with patch(
        "zrb.builtin.shell.autocomplete.subcmd.get_group_subcommands",
        return_value=mock_subcommands,
    ):
        res = _action(get_shell_subcommands)(ctx)
        assert res == "cmd1 cmd2"


def test_get_shell_subcommands_not_found():
    ctx = MagicMock()
    ctx.args = ["nonexistent"]

    with patch(
        "zrb.builtin.shell.autocomplete.subcmd.get_group_subcommands", return_value=[]
    ):
        res = _action(get_shell_subcommands)(ctx)
        assert res == ""

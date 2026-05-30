from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.shell.autocomplete.subcmd import get_shell_subcommands


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
        res = get_shell_subcommands._action(ctx)
        assert res == "cmd1 cmd2"


def test_get_shell_subcommands_not_found():
    ctx = MagicMock()
    ctx.args = ["nonexistent"]

    with patch(
        "zrb.builtin.shell.autocomplete.subcmd.get_group_subcommands", return_value=[]
    ):
        res = get_shell_subcommands._action(ctx)
        assert res == ""

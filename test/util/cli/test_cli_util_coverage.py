from unittest.mock import MagicMock, patch

import pytest

from zrb.group.group import Group
from zrb.util.cli.subcommand import SubCommand, get_group_subcommands
from zrb.util.cli.text import edit_text


def test_subcommand_repr():
    sc = SubCommand(paths=["a", "b"], nexts=["c"])
    assert "SubCommand" in repr(sc)
    assert "paths=['a', 'b']" in repr(sc)
    assert "nexts=['c']" in repr(sc)


def test_get_group_subcommands_empty():
    group = Group(name="root")
    subcommands = get_group_subcommands(group)
    assert subcommands == []


@patch("subprocess.call")
@patch("zrb.util.cli.text.read_file")
def test_edit_text(mock_read_file, mock_subprocess_call):
    mock_read_file.return_value = "edited content"
    mock_subprocess_call.return_value = 0

    result = edit_text(prompt_message="Prompt", value="initial", editor="mock-editor")

    assert result == "edited content"
    mock_subprocess_call.assert_called()

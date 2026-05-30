from unittest.mock import MagicMock, patch

import pytest

from zrb.util.cli.subcommand import SubCommand, get_group_subcommands
from zrb.util.cli.text import edit_text


def test_subcommand_repr():
    sc = SubCommand(paths=["a", "b"], nexts=["c"])
    assert "SubCommand" in repr(sc)
    assert "paths=['a', 'b']" in repr(sc)
    assert "nexts=['c']" in repr(sc)


def test_get_group_subcommands_empty():
    # Use a minimal mock object instead of real Group
    mock_group = MagicMock()
    mock_group.name = "root"

    with patch("zrb.util.cli.subcommand.get_subtasks", return_value=[]), patch(
        "zrb.util.cli.subcommand.get_non_empty_subgroups", return_value={}
    ):
        subcommands = get_group_subcommands(mock_group)
        assert subcommands == []


def test_get_group_subcommands_with_tasks():
    """Test get_group_subcommands with tasks in group."""
    mock_group = MagicMock()
    mock_group.name = "root"

    # Mock get_subtasks to return task aliases
    with patch(
        "zrb.util.cli.subcommand.get_subtasks", return_value=["task1", "task2"]
    ), patch("zrb.util.cli.subcommand.get_non_empty_subgroups", return_value={}):

        # Pass empty subcommands list to ensure isolation if fix was missing
        subcommands = get_group_subcommands(mock_group, subcommands=[])

        assert len(subcommands) == 1
        assert subcommands[0].paths == ["root"]
        assert set(subcommands[0].nexts) == {"task1", "task2"}


def test_get_group_subcommands_with_subgroups():
    """Test get_group_subcommands with nested subgroups."""
    root_group = MagicMock()
    root_group.name = "root"
    child_group = MagicMock()
    child_group.name = "child"

    def get_subtasks_side_effect(group):
        if group == root_group:
            return []
        if group == child_group:
            return ["child-task1"]
        return []

    def get_non_empty_subgroups_side_effect(group):
        if group == root_group:
            return {"child": child_group}
        return {}

    # Mock get_subtasks and get_non_empty_subgroups
    with patch(
        "zrb.util.cli.subcommand.get_subtasks", side_effect=get_subtasks_side_effect
    ), patch(
        "zrb.util.cli.subcommand.get_non_empty_subgroups",
        side_effect=get_non_empty_subgroups_side_effect,
    ):

        subcommands = get_group_subcommands(root_group, subcommands=[])

        assert len(subcommands) >= 2

        root_sc = next(sc for sc in subcommands if sc.paths == ["root"])
        assert "child" in root_sc.nexts

        child_sc = next(sc for sc in subcommands if sc.paths == ["root", "child"])
        assert "child-task1" in child_sc.nexts


def test_subcommand_init_defaults():
    """Test SubCommand initialization with default values."""
    sc = SubCommand()
    assert sc.paths == []
    assert sc.nexts == []


@patch("subprocess.call")
@patch("zrb.util.cli.text.read_file")
def test_edit_text(mock_read_file, mock_subprocess_call):
    mock_read_file.return_value = "edited content"
    mock_subprocess_call.return_value = 0

    result = edit_text(prompt_message="Prompt", value="initial", editor="mock-editor")

    assert result == "edited content"
    mock_subprocess_call.assert_called()

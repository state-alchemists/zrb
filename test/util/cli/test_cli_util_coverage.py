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


def test_get_group_subcommands_with_tasks():
    """Test get_group_subcommands with tasks in group."""
    group = Group(name="root")
    
    # Mock tasks
    task1 = MagicMock()
    task1.name = "task1"
    task1.aliases = ["task1"]
    
    task2 = MagicMock()
    task2.name = "task2"
    task2.aliases = ["task2"]
    
    # Mock get_subtasks to return task aliases
    with patch("zrb.util.cli.subcommand.get_subtasks") as mock_get_subtasks:
        with patch("zrb.util.cli.subcommand.get_non_empty_subgroups") as mock_get_subgroups:
            mock_get_subtasks.return_value = ["task1", "task2"]
            mock_get_subgroups.return_value = {}
            
            subcommands = get_group_subcommands(group)
            
            assert len(subcommands) == 1
            assert subcommands[0].paths == ["root"]
            assert set(subcommands[0].nexts) == {"task1", "task2"}


def test_get_group_subcommands_with_subgroups():
    """Test get_group_subcommands with nested subgroups."""
    root_group = Group(name="root")
    child_group = Group(name="child")
    
    # Mock get_subtasks and get_non_empty_subgroups
    with patch("zrb.util.cli.subcommand.get_subtasks") as mock_get_subtasks:
        with patch("zrb.util.cli.subcommand.get_non_empty_subgroups") as mock_get_subgroups:
            # Root group has no tasks but has a child group
            mock_get_subtasks.return_value = []
            mock_get_subgroups.return_value = {"child": child_group}
            
            # Child group has tasks
            def get_subtasks_side_effect(group):
                if group == root_group:
                    return []
                elif group == child_group:
                    return ["child-task1", "child-task2"]
                return []
            
            def get_non_empty_subgroups_side_effect(group):
                if group == root_group:
                    return {"child": child_group}
                return {}
            
            mock_get_subtasks.side_effect = get_subtasks_side_effect
            mock_get_subgroups.side_effect = get_non_empty_subgroups_side_effect
            
            subcommands = get_group_subcommands(root_group)
            
            # Should have 3 subcommands: root (with child), child, and root (empty - from recursive call)
            # The function adds a subcommand when nexts > 0, and it's called recursively
            assert len(subcommands) >= 2
            
            # Find root subcommand with child as next
            root_with_child = next((sc for sc in subcommands if sc.paths == ["root"] and "child" in sc.nexts), None)
            assert root_with_child is not None
            assert "child" in root_with_child.nexts
            
            # Find child subcommand
            child_subcommand = next((sc for sc in subcommands if sc.paths == ["root", "child"]), None)
            assert child_subcommand is not None
            assert set(child_subcommand.nexts) == {"child-task1", "child-task2"}


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

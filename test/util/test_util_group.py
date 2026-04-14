"""Tests for util/group.py - Group utility functions."""

from unittest.mock import MagicMock

import pytest


class TestNodeNotFoundError:
    """Test NodeNotFoundError exception."""

    def test_is_value_error(self):
        """Test that NodeNotFoundError is a ValueError."""
        from zrb.util.group import NodeNotFoundError

        assert issubclass(NodeNotFoundError, ValueError)

    def test_can_raise(self):
        """Test that NodeNotFoundError can be raised."""
        from zrb.util.group import NodeNotFoundError

        with pytest.raises(NodeNotFoundError):
            raise NodeNotFoundError("Node not found")


class TestExtractNodeFromArgs:
    """Test extract_node_from_args function."""

    def test_extract_task(self):
        """Test extracting a task from args."""
        from zrb.util.group import extract_node_from_args

        root = MagicMock()
        task = MagicMock()
        task.name = "my_task"
        root.get_task_by_alias.return_value = task
        root.get_group_by_alias.return_value = None

        node, path, residual = extract_node_from_args(root, ["my_task"])
        assert node == task
        assert path == ["my_task"]
        assert residual == []

    def test_web_only_skips_cli_only_task(self):
        """Test that web_only=True skips cli_only tasks."""
        from zrb.util.group import NodeNotFoundError, extract_node_from_args

        root = MagicMock()
        root.name = "root"
        cli_task = MagicMock()
        cli_task.cli_only = True
        # get_task_by_alias returns a cli_only task, which should be filtered
        root.get_task_by_alias.return_value = cli_task
        root.get_group_by_alias.return_value = None

        with pytest.raises(NodeNotFoundError):
            extract_node_from_args(root, ["cli_task"], web_only=True)

    def test_web_only_skips_empty_group(self):
        """Test that web_only=True skips groups with no web tasks."""
        from zrb.util.group import NodeNotFoundError, extract_node_from_args

        root = MagicMock()
        root.name = "root"
        # No task
        root.get_task_by_alias.return_value = None
        # Empty group (no subtasks)
        empty_group = MagicMock()
        empty_group.subtasks = {}
        empty_group.subgroups = {}
        root.get_group_by_alias.return_value = empty_group

        with pytest.raises(NodeNotFoundError):
            extract_node_from_args(root, ["empty_group"], web_only=True)

    def test_both_task_and_group_at_last_position(self):
        """Test that when both task and group exist at last arg position, task wins."""
        from zrb.util.group import extract_node_from_args

        root = MagicMock()
        task = MagicMock()
        task.cli_only = False
        group = MagicMock()
        # Return both task and group for the same alias
        root.get_task_by_alias.return_value = task
        root.get_group_by_alias.return_value = group

        # This is the last arg, so task should be preferred over group
        node, path, residual = extract_node_from_args(root, ["ambiguous"])
        assert node == task  # task wins when both exist at last position

    def test_extract_group(self):
        """Test extracting a group from args."""
        from zrb.util.group import extract_node_from_args

        root = MagicMock()
        subgroup = MagicMock()
        subgroup.name = "subgroup"

        root.get_task_by_alias.return_value = None
        root.get_group_by_alias.return_value = subgroup

        subgroup.get_task_by_alias.return_value = None
        subgroup.get_group_by_alias.return_value = None

        node, path, residual = extract_node_from_args(root, ["subgroup"])
        assert node == subgroup
        assert path == ["subgroup"]

    def test_extract_nonexistent_raises(self):
        """Test that nonexistent node raises NodeNotFoundError."""
        from zrb.util.group import NodeNotFoundError, extract_node_from_args

        root = MagicMock()
        root.name = "root"
        root.get_task_by_alias.return_value = None
        root.get_group_by_alias.return_value = None

        with pytest.raises(NodeNotFoundError):
            extract_node_from_args(root, ["nonexistent"])

    def test_extract_with_residual_args(self):
        """Test extraction with residual arguments."""
        from zrb.util.group import extract_node_from_args

        root = MagicMock()
        task = MagicMock()
        root.get_task_by_alias.return_value = task
        root.get_group_by_alias.return_value = None

        node, path, residual = extract_node_from_args(root, ["task", "arg1", "arg2"])
        assert node == task
        assert residual == ["arg1", "arg2"]


class TestGetNodePath:
    """Test get_node_path function."""

    def test_get_node_path_none_group(self):
        """Test get_node_path with None group."""
        from zrb.util.group import get_node_path

        task = MagicMock()
        result = get_node_path(None, task)
        assert result == []

    def test_get_node_path_same_node(self):
        """Test get_node_path when node is the same as group."""
        from zrb.util.group import get_node_path

        group = MagicMock()
        group.name = "root"

        result = get_node_path(group, group)
        assert result == ["root"]

    def test_get_node_path_subtask(self):
        """Test get_node_path finding a subtask."""
        from zrb.task.any_task import AnyTask
        from zrb.util.group import get_node_path

        group = MagicMock()
        # Create a spec mock that passes isinstance check
        task = MagicMock(spec=AnyTask)
        group.subtasks = {"task_alias": task}
        group.subgroups = {}

        result = get_node_path(group, task)
        assert result == ["task_alias"]

    def test_get_node_path_not_found(self):
        """Test get_node_path when node not found."""
        from zrb.util.group import get_node_path

        group = MagicMock()
        group.subtasks = {}
        group.subgroups = {}

        task = MagicMock()
        result = get_node_path(group, task)
        assert result is None

    def test_get_node_path_direct_subgroup(self):
        """Test get_node_path finding a direct subgroup."""
        from zrb.group.any_group import AnyGroup
        from zrb.util.group import get_node_path

        group = MagicMock()
        subgroup = MagicMock(spec=AnyGroup)
        group.subtasks = {}
        group.subgroups = {"subgroup_alias": subgroup}

        result = get_node_path(group, subgroup)
        assert result == ["subgroup_alias"]

    def test_get_node_path_nested_subgroup(self):
        """Test get_node_path finding a nested subgroup."""
        from zrb.group.any_group import AnyGroup
        from zrb.task.any_task import AnyTask
        from zrb.util.group import get_node_path

        root = MagicMock()
        mid = MagicMock()
        # deep_task is the target
        deep_task = MagicMock(spec=AnyTask)

        mid.subtasks = {"deep_task": deep_task}
        mid.subgroups = {}

        root.subtasks = {}
        root.subgroups = {"mid": mid}

        result = get_node_path(root, deep_task)
        assert result == ["mid", "deep_task"]


class TestGetNonEmptySubgroups:
    """Test get_non_empty_subgroups function."""

    def test_get_non_empty_subgroups(self):
        """Test getting subgroups with tasks."""
        from zrb.util.group import get_non_empty_subgroups

        group = MagicMock()
        task = MagicMock()
        task.cli_only = False

        subgroup_with_task = MagicMock()
        subgroup_with_task.subtasks = {"task": task}
        subgroup_with_task.subgroups = {}

        subgroup_empty = MagicMock()
        subgroup_empty.subtasks = {}
        subgroup_empty.subgroups = {}

        group.subgroups = {"with_task": subgroup_with_task, "empty": subgroup_empty}
        group.subtasks = {}

        result = get_non_empty_subgroups(group, web_only=False)
        assert "with_task" in result
        assert "empty" not in result


class TestGetSubtasks:
    """Test get_subtasks function."""

    def test_get_subtasks(self):
        """Test getting all subtasks."""
        from zrb.util.group import get_subtasks

        group = MagicMock()
        task1 = MagicMock()
        task1.cli_only = False
        task2 = MagicMock()
        task2.cli_only = True

        group.subtasks = {"task1": task1, "task2": task2}

        result = get_subtasks(group, web_only=False)
        assert "task1" in result
        assert "task2" in result

    def test_get_subtasks_web_only(self):
        """Test getting subtasks with web_only filter."""
        from zrb.util.group import get_subtasks

        group = MagicMock()
        task1 = MagicMock()
        task1.cli_only = False
        task2 = MagicMock()
        task2.cli_only = True

        group.subtasks = {"task1": task1, "task2": task2}

        result = get_subtasks(group, web_only=True)
        assert "task1" in result
        assert "task2" not in result


class TestGetAllSubtasks:
    """Test get_all_subtasks function."""

    def test_get_all_subtasks_direct(self):
        """Test getting all direct subtasks."""
        from zrb.util.group import get_all_subtasks

        group = MagicMock()
        task1 = MagicMock()
        task1.cli_only = False
        task2 = MagicMock()
        task2.cli_only = False

        group.subtasks = {"task1": task1, "task2": task2}
        group.subgroups = {}

        result = get_all_subtasks(group, web_only=False)
        assert task1 in result
        assert task2 in result

    def test_get_all_subtasks_nested(self):
        """Test getting all nested subtasks."""
        from zrb.util.group import get_all_subtasks

        group = MagicMock()
        task1 = MagicMock()
        task1.cli_only = False

        subgroup = MagicMock()
        task2 = MagicMock()
        task2.cli_only = False
        subgroup.subtasks = {"task2": task2}
        subgroup.subgroups = {}

        group.subtasks = {"task1": task1}
        group.subgroups = {"sub": subgroup}

        result = get_all_subtasks(group, web_only=False)
        assert task1 in result
        assert task2 in result

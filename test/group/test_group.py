import pytest

from zrb.group.any_group import NodeNotFoundError
from zrb.group.group import Group
from zrb.task.base.base_task import BaseTask


def test_remove_group_by_alias_and_name():
    parent_group = Group(name="parent")
    group1 = Group(name="test_group", description="Test Group")
    parent_group.add_group(group1, alias="same_name")
    parent_group.remove_group("same_name")
    assert parent_group.get_group_by_alias("same_name") is None

    group2 = Group(name="test_group2", description="Test Group 2")
    parent_group.add_group(group2, alias="alias2")
    parent_group.remove_group("test_group2")
    assert parent_group.get_group_by_alias("alias2") is None

    group3 = Group(name="same_alias", description="Test Group 3")
    parent_group.add_group(group3, alias="same_alias")
    parent_group.remove_group("same_alias")
    assert parent_group.get_group_by_alias("same_alias") is None


def test_remove_group_by_object():
    parent_group = Group(name="parent")
    group1 = Group(name="group1")
    parent_group.add_group(group1)

    parent_group.remove_group(group1)
    assert parent_group.get_group_by_alias("group1") is None


def test_remove_group_by_object_raises_error():
    parent_group = Group(name="parent")
    group1 = Group(name="group1")
    # Not added

    with pytest.raises(ValueError):
        parent_group.remove_group(group1)


def test_remove_group_raises_value_error():
    parent_group = Group(name="parent")
    with pytest.raises(ValueError):
        parent_group.remove_group("non_existent_group")


def test_remove_task_by_alias_and_name():
    parent_group = Group(name="parent")
    task1 = BaseTask(name="test_task")
    parent_group.add_task(task1, alias="same_name")
    parent_group.remove_task("same_name")
    assert parent_group.get_task_by_alias("same_name") is None

    task2 = BaseTask(name="test_task2")
    parent_group.add_task(task2, alias="alias2")
    parent_group.remove_task("test_task2")
    assert parent_group.get_task_by_alias("alias2") is None

    task3 = BaseTask(name="same_alias")
    parent_group.add_task(task3, alias="same_alias")
    parent_group.remove_task("same_alias")
    assert parent_group.get_task_by_alias("same_alias") is None


def test_remove_task_by_object():
    parent_group = Group(name="parent")
    task1 = BaseTask(name="task1")
    parent_group.add_task(task1)

    parent_group.remove_task(task1)
    assert parent_group.get_task_by_alias("task1") is None


def test_remove_task_by_object_raises_error():
    parent_group = Group(name="parent")
    task1 = BaseTask(name="task1")
    # Not added

    with pytest.raises(ValueError):
        parent_group.remove_task(task1)


def test_remove_task_raises_value_error():
    parent_group = Group(name="parent")
    with pytest.raises(ValueError):
        parent_group.remove_task("non_existent_task")


def test_get_task_by_alias():
    parent_group = Group(name="parent")
    task1 = BaseTask(name="test_task")
    parent_group.add_task(task1, alias="alias1")
    assert parent_group.get_task_by_alias("alias1") == task1
    assert parent_group.get_task_by_alias("non_existent_alias") is None


def test_get_group_by_alias():
    parent_group = Group(name="parent")
    group1 = Group(name="test_group")
    parent_group.add_group(group1, alias="alias1")
    assert parent_group.get_group_by_alias("alias1") == group1
    assert parent_group.get_group_by_alias("non_existent_alias") is None


def test_subgroups():
    parent_group = Group(name="parent")
    group1 = Group(name="test_group")
    group2 = Group(name="test_group2")
    parent_group.add_group(group1)
    parent_group.add_group(group2)
    subgroups = parent_group.subgroups
    assert list(subgroups.keys()) == ["test_group", "test_group2"]
    assert subgroups["test_group"] == group1
    assert subgroups["test_group2"] == group2


def test_subtasks():
    parent_group = Group(name="parent")
    task1 = BaseTask(name="test_task")
    task2 = BaseTask(name="test_task2")
    parent_group.add_task(task1)
    parent_group.add_task(task2)
    subtasks = parent_group.subtasks
    assert list(subtasks.keys()) == ["test_task", "test_task2"]
    assert subtasks["test_task"] == task1
    assert subtasks["test_task2"] == task2


def test_name():
    group = Group(name="test_group")
    assert group.name == "test_group"


def test_banner():
    group = Group(name="test_group", banner="test_banner")
    assert group.banner == "test_banner"
    group = Group(name="test_group")
    assert group.banner == ""


def test_description():
    group = Group(name="test_group", description="test_description")
    assert group.description == "test_description"
    group = Group(name="test_group")
    assert group.description == "test_group"


def test_add_group():
    parent_group = Group(name="parent")
    group1 = Group(name="test_group")
    parent_group.add_group(group1)
    assert parent_group.get_group_by_alias("test_group") == group1
    group2 = Group(name="test_group2")
    parent_group.add_group(group2, alias="alias2")
    assert parent_group.get_group_by_alias("alias2") == group2


def test_add_group_from_string():
    parent = Group(name="parent")
    parent.add_group("child")
    assert parent.get_group_by_alias("child").name == "child"


def test_add_task():
    parent_group = Group(name="parent")
    task1 = BaseTask(name="test_task")
    parent_group.add_task(task1)
    assert parent_group.get_task_by_alias("test_task") == task1
    task2 = BaseTask(name="test_task2")
    parent_group.add_task(task2, alias="alias2")
    assert parent_group.get_task_by_alias("alias2") == task2


def test_repr():
    g = Group(name="foo")
    assert repr(g) == "<Group name=foo>"


def test_get_node_path_same_node():
    group = Group(name="root")
    assert group.get_node_path(group) == ["root"]


def test_get_node_path_subtask():
    group = Group(name="root")
    task = BaseTask(name="task")
    group.add_task(task, alias="task_alias")
    assert group.get_node_path(task) == ["task_alias"]


def test_get_node_path_not_found():
    group = Group(name="root")
    task = BaseTask(name="task")
    assert group.get_node_path(task) is None


def test_get_node_path_direct_subgroup():
    group = Group(name="root")
    subgroup = Group(name="sub")
    group.add_group(subgroup, alias="subgroup_alias")
    assert group.get_node_path(subgroup) == ["subgroup_alias"]


def test_get_node_path_nested_subgroup():
    root = Group(name="root")
    mid = Group(name="mid")
    root.add_group(mid)
    deep_task = BaseTask(name="deep_task")
    mid.add_task(deep_task)
    assert root.get_node_path(deep_task) == ["mid", "deep_task"]


def test_get_subtasks_web_only():
    group = Group(name="root")
    task1 = BaseTask(name="task1")
    task2 = BaseTask(name="task2", cli_only=True)
    group.add_task(task1)
    group.add_task(task2)

    assert set(group.get_subtasks().keys()) == {"task1", "task2"}
    assert set(group.get_subtasks(web_only=True).keys()) == {"task1"}


def test_get_all_subtasks_nested():
    group = Group(name="root")
    task1 = BaseTask(name="task1")
    group.add_task(task1)
    subgroup = Group(name="sub")
    task2 = BaseTask(name="task2")
    subgroup.add_task(task2)
    group.add_group(subgroup)

    all_subtasks = group.get_all_subtasks()
    assert task1 in all_subtasks
    assert task2 in all_subtasks


def test_get_non_empty_subgroups():
    group = Group(name="root")
    with_task = Group(name="with_task")
    with_task.add_task(BaseTask(name="task"))
    empty = Group(name="empty")
    group.add_group(with_task)
    group.add_group(empty)

    non_empty = group.get_non_empty_subgroups()
    assert "with_task" in non_empty
    assert "empty" not in non_empty


def test_extract_node_task():
    root = Group(name="root")
    task = BaseTask(name="my_task")
    root.add_task(task)

    node, path, residual = root.extract_node(["my_task"])
    assert node == task
    assert path == ["my_task"]
    assert residual == []


def test_extract_node_with_residual_args():
    root = Group(name="root")
    task = BaseTask(name="my_task")
    root.add_task(task)

    node, path, residual = root.extract_node(["my_task", "arg1", "arg2"])
    assert node == task
    assert residual == ["arg1", "arg2"]


def test_extract_node_group():
    root = Group(name="root")
    subgroup = Group(name="subgroup")
    root.add_group(subgroup)

    node, path, residual = root.extract_node(["subgroup"])
    assert node == subgroup
    assert path == ["subgroup"]


def test_extract_node_nonexistent_raises():
    root = Group(name="root")
    with pytest.raises(NodeNotFoundError):
        root.extract_node(["nonexistent"])


def test_extract_node_web_only_skips_cli_only_task():
    root = Group(name="root")
    root.add_task(BaseTask(name="cli_task", cli_only=True))
    with pytest.raises(NodeNotFoundError):
        root.extract_node(["cli_task"], web_only=True)


def test_extract_node_web_only_skips_empty_group():
    root = Group(name="root")
    root.add_group(Group(name="empty_group"))
    with pytest.raises(NodeNotFoundError):
        root.extract_node(["empty_group"], web_only=True)

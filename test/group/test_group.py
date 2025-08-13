import pytest

from zrb.group.group import Group
from zrb.task.base_task import BaseTask


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


def test_add_task():
    parent_group = Group(name="parent")
    task1 = BaseTask(name="test_task")
    parent_group.add_task(task1)
    assert parent_group.get_task_by_alias("test_task") == task1
    task2 = BaseTask(name="test_task2")
    parent_group.add_task(task2, alias="alias2")
    assert parent_group.get_task_by_alias("alias2") == task2

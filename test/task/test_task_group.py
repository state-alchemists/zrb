from zrb.task_group.group import Group
from zrb.task.task import Task


def test_init_simple_group():
    group = Group(name='group')
    assert group._get_full_cli_name() == 'group'
    assert group.get_description() == ''
    assert len(group.get_children()) == 0
    assert group.get_parent() is None
    assert str(group) == '<Group "group">'


def test_init_simple_group_with_description():
    group = Group(name='group', description='description')
    assert group._get_full_cli_name() == 'group'
    assert group.get_description() == 'description'
    assert len(group.get_children()) == 0
    assert group.get_parent() is None


def test_init_group_with_parent():
    grand_parent = Group(name='grand-parent')
    parent = Group(name='parent', parent=grand_parent)
    group = Group(name='group', parent=parent)
    assert group._get_full_cli_name() == 'grand-parent parent group'
    assert group.get_description() == ''
    assert len(group.get_children()) == 0
    assert group.get_parent()._get_full_cli_name() == 'grand-parent parent'
    assert str(group) == '<Group "grand-parent parent group">'


def test_group_with_children():
    group = Group(name='group')
    child_1 = Group(name='child-1', parent=group)
    child_2 = Group(name='child-2', parent=group)
    children = group.get_children()
    assert len(children) == 2
    assert children[0] == child_1
    assert children[1] == child_2
    assert group.get_parent() is None


def test_init_group_with_task():
    group = Group(name='group')
    task_1 = Task(name='task_1', group=group)
    task_2 = Task(name='task_2', group=group)
    tasks = group.get_tasks()
    assert len(tasks) == 2
    assert tasks[0] == task_1
    assert tasks[1] == task_2

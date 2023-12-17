from zrb.task_group.group import Group


def test_init_simple_group():
    group = Group(name='group')
    assert group._get_full_cli_name() == 'group'
    assert group.get_description() == ''
    assert len(group.get_children()) == 0
    assert len(group.get_parent()) is None


def test_init_simple_group():
    group = Group(name='group')
    assert group._get_full_cli_name() == 'group'
    assert group.get_description() == ''
    assert len(group.get_children()) == 0
    assert len(group.get_parent()) is None


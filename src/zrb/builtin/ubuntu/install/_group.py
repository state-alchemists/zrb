from zrb.builtin.ubuntu._group import ubuntu_group
from zrb.task_group.group import Group

ubuntu_install_group = Group(
    name="install", description="Install things on ubuntu", parent=ubuntu_group
)

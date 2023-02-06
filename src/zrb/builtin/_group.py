from ..task_group.group import Group

project_group = Group(
    name='project', description='Project related commands'
)
task_group = Group(
    name='task', description='Task related commands'
)
env_group = Group(
    name='env', description='Env related commands'
)
ubuntu_group = Group(
    name='ubuntu', description='Ubuntu related commands'
)
ubuntu_install_group = Group(
    name='install', description='Install things on ubuntu', parent=ubuntu_group
)
principle_group = Group(
    name='principle', description='Principle related commands'
)
principle_show_group = Group(
    name='show', description='Showing principles', parent=principle_group
)

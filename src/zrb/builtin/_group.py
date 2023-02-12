from ..task_group.group import Group

project_group = Group(
    name='project', description='Project management'
)
task_group = Group(
    name='task', description='Task management'
)
env_group = Group(
    name='env', description='Environment variable management'
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
base64_group = Group(
    name='base64', description='Base64 operations'
)
md5_group = Group(
    name='md5', description='MD5 operations'
)
dev_tool_group = Group(
    name='devtool', description='Developer tools management'
)
dev_tool_install_group = Group(
    name='install', description='Install developer tools',
    parent=dev_tool_group
)

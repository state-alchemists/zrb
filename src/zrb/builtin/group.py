from zrb.task_group.group import Group

project_group = Group(name="project", description="Project management")
project_add_group = Group(
    name="add", description="Add resources to project", parent=project_group
)
ubuntu_group = Group(name="ubuntu", description="Ubuntu related commands")
ubuntu_install_group = Group(
    name="install", description="Install things on ubuntu", parent=ubuntu_group
)
md5_group = Group(name="md5", description="MD5 operations")
process_group = Group(name="process", description="Process related commands")
plugin_group = Group(name="plugin", description="Plugin related command")

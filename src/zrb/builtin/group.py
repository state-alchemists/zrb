from zrb.task_group.group import Group

project_group = Group(name="project", description="Project management")
project_add_group = Group(
    name="add", description="Add resources to project", parent=project_group
)
env_group = Group(name="env", description="Environment variable management")
ubuntu_group = Group(name="ubuntu", description="Ubuntu related commands")
ubuntu_install_group = Group(
    name="install", description="Install things on ubuntu", parent=ubuntu_group
)
explain_group = Group(name="explain", description="Explain things")
base64_group = Group(name="base64", description="Base64 operations")
md5_group = Group(name="md5", description="MD5 operations")
dev_tool_group = Group(name="devtool", description="Developer tools management")
dev_tool_install_group = Group(
    name="install", description="Install developer tools", parent=dev_tool_group
)
git_group = Group(name="git", description="Git related commands")
docker_group = Group(name="docker", description="Docker related commands")
process_group = Group(name="process", description="Process related commands")
plugin_group = Group(name="plugin", description="Plugin related command")

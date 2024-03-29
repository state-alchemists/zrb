from zrb.task_group.group import Group
from zrb.builtin.devtool._group import devtool_group

dev_tool_install_group = Group(
    name="install", description="Install developer tools", parent=devtool_group
)

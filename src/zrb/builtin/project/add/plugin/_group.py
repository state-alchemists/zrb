from zrb.builtin.project.add._group import project_add_group
from zrb.task_group.group import Group

project_add_plugin_group = Group(
    name="plugin", description="Add plugin to project", parent=project_add_group
)

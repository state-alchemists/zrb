from zrb.builtin.project.add._group import project_add_group
from zrb.task_group.group import Group

project_add_app_group = Group(
    name="app", description="Add app/generator to project", parent=project_add_group
)

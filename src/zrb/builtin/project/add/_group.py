from zrb.builtin.project._group import project_group
from zrb.task_group.group import Group

project_add_group = Group(
    name="add", description="Add resources to project", parent=project_group
)

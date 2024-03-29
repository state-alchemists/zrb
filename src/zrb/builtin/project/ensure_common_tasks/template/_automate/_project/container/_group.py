from zrb.builtin.project._group import project_group
from zrb.task_group.group import Group

project_container_group = Group(
    name="container", description="Container related tasks", parent=project_group
)

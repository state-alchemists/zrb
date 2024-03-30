from zrb.builtin.project.add._group import project_add_group
from zrb.task_group.group import Group

project_add_task_group = Group(
    name="task", description="Add task to project", parent=project_add_group
)

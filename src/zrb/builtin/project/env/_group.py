from zrb.builtin.project._group import project_group
from zrb.task_group.group import Group

project_env_group = Group(
    name="env", description="Project environments", parent=project_group
)

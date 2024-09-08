from zrb.builtin.project._group import project_group
from zrb.task_group import Group

project_monorepo_group = Group(
    name="monorepo", parent=project_group, description="Project monorepo manageemnt"
)

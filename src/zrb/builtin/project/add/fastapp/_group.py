from zrb import Group
from zrb.builtin.project.add._group import project_add_group

project_add_fastapp_group = Group(
    name="fastapp",
    description="Add fastapp related resources",
    parent=project_add_group,
)

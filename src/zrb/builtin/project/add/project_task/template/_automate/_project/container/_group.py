from zrb import Group
from zrb.builtin import project_group

project_container_group = Group(
    name="container", parent=project_group, description="Manage project containers"
)

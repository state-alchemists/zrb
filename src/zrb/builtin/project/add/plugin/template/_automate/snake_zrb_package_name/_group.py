from zrb import Group
from zrb.builtin import project_group

snake_zrb_package_name_group = Group(
    name="snake_zrb_package_name",
    parent=project_group,
    description="Manage human readable zrb package name",
)

from zrb import Group
from zrb.builtin import project_group

snake_zrb_app_name_group = Group(
    name="kebab-zrb-app-name",
    parent=project_group,
    description="Manage human readable zrb app name",
)

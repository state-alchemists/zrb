from zrb import Group

from .._group import snake_zrb_app_name_container_group

snake_zrb_app_name_support_container_group = Group(
    name="support",
    parent=snake_zrb_app_name_container_group,
    description="Manage human readable zrb app name support containers",
)

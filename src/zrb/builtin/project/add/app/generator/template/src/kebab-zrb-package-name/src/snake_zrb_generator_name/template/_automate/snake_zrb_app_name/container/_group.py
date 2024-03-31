from zrb import Group

from .._group import snake_zrb_app_name_group

snake_zrb_app_name_container_group = Group(
    name="container",
    parent=snake_zrb_app_name_group,
    description="Manage human readable zrb app name containers",
)

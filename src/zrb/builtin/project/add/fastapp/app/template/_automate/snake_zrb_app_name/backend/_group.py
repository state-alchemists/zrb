from zrb import Group

from .._group import snake_zrb_app_name_group

snake_zrb_app_name_backend_group = Group(
    name="backend",
    parent=snake_zrb_app_name_group,
    description="Manage human readable zrb app name backend",
)

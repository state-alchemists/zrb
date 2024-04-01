from zrb import Group

from .._group import snake_zrb_app_name_group

snake_zrb_app_name_monolith_group = Group(
    name="monolith",
    parent=snake_zrb_app_name_group,
    description="Manage human readable zrb app name as monolith",
)

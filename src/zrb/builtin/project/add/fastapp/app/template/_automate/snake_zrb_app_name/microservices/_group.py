from zrb import Group

from .._group import snake_zrb_app_name_group

snake_zrb_app_name_microservices_group = Group(
    name="microservices",
    parent=snake_zrb_app_name_group,
    description="Manage human readable zrb app name as microservices",
)

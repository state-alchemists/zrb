from zrb import Group

from .._group import snake_zrb_app_name_group

snake_zrb_app_name_image_group = Group(
    name="image",
    parent=snake_zrb_app_name_group,
    description="Manage human readable zrb app name images",
)

from zrb import Group
from zrb.builtin import project_group

project_image_group = Group(
    name="image", parent=project_group, description="Manage project images"
)

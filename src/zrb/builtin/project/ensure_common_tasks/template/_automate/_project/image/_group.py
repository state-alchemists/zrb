from zrb.builtin.project._group import project_group
from zrb.task_group.group import Group

project_image_group = Group(
    name="image", description="Image related tasks", parent=project_group
)

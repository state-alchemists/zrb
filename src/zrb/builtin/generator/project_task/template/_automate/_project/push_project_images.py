from zrb.builtin._group import project_group
from zrb import Task, runner

push_project_images = Task(
    name='push-images',
    group=project_group,
    upstreams=[],
    description='Build project images'
)
runner.register(push_project_images)

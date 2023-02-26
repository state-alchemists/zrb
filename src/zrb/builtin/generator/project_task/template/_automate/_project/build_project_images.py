from zrb.builtin._group import project_group
from zrb import Task, runner

build_project_images = Task(
    name='build-images',
    group=project_group,
    upstreams=[],
    description='Build project images'
)
runner.register(build_project_images)

from zrb.builtin.group import project_group
from zrb import Task, runner

build_project_images = Task(
    name='build-images',
    group=project_group,
    upstreams=[],
    description='Build project images',
    run=lambda *args, **kwargs: kwargs.get('_task').print_out('🆗')
)
runner.register(build_project_images)

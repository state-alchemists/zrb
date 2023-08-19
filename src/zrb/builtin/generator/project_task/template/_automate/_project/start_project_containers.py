from zrb.builtin.group import project_group
from zrb import Task, runner

start_project_containers = Task(
    name='start-containers',
    group=project_group,
    upstreams=[],
    description='Start as containers',
    run=lambda *args, **kwargs: kwargs.get('_task').print_out('🆗')
)
runner.register(start_project_containers)

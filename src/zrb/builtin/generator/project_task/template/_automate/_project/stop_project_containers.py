from zrb.builtin.group import project_group
from zrb import Task, runner

stop_project_containers = Task(
    name='stop-containers',
    group=project_group,
    upstreams=[],
    description='Stop project containers',
    run=lambda *args, **kwargs: kwargs.get('_task').print_out('🆗')
)
runner.register(stop_project_containers)

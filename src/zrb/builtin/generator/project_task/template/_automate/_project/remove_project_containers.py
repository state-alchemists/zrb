from zrb.builtin.group import project_group
from zrb import Task, runner

remove_project_containers = Task(
    name='remove-containers',
    group=project_group,
    upstreams=[],
    description='Remove project containers',
    run=lambda *args, **kwargs: kwargs.get('_task').print_out('🆗')
)
runner.register(remove_project_containers)

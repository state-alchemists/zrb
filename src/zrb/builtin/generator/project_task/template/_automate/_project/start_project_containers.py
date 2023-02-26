from zrb.builtin._group import project_group
from zrb import Task, runner

start_project_containers = Task(
    name='start-containers',
    group=project_group,
    upstreams=[],
    description='Start as containers'
)
runner.register(start_project_containers)

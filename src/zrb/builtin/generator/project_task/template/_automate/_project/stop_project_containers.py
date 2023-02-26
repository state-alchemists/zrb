from zrb.builtin._group import project_group
from zrb import Task, runner

stop_project_containers = Task(
    name='stop-containers',
    group=project_group,
    upstreams=[],
    description='Stop project containers'
)
runner.register(stop_project_containers)

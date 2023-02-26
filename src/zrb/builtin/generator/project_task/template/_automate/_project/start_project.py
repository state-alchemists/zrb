from zrb.builtin._group import project_group
from zrb import Task, runner

start_project = Task(
    name='start',
    group=project_group,
    upstreams=[],
    description='Start project'
)
runner.register(start_project)

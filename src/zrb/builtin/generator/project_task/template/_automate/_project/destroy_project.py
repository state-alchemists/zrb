from zrb.builtin._group import project_group
from zrb import Task, runner

destroy_project = Task(
    name='destroy',
    group=project_group,
    upstreams=[],
    description='Remove project deployment'
)
runner.register(destroy_project)

from zrb.builtin._group import project_group
from zrb import Task, runner

remove_project_deployment = Task(
    name='remove-deployment',
    group=project_group,
    upstreams=[],
    description='Remove project deployment'
)
runner.register(remove_project_deployment)

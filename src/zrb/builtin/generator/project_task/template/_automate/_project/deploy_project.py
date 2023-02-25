from zrb.builtin._group import project_group
from zrb import Task, runner

deploy_project = Task(
    name='deploy',
    group=project_group,
    upstreams=[]
)
runner.register(deploy_project)

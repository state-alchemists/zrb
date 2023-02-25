from zrb.builtin._group import project_group
from zrb import Task, runner

start_project = Task(
    name='start',
    group=project_group,
    upstreams=[]
)
runner.register(start_project)

start_project_containers = Task(
    name='start-containers',
    group=project_group,
    upstreams=[]
)
runner.register(start_project_containers)

remove_project_containers = Task(
    name='remove-containers',
    group=project_group,
    upstreams=[]
)
runner.register(remove_project_containers)


deploy_project = Task(
    name='deploy',
    group=project_group,
    upstreams=[]
)
runner.register(deploy_project)

remove_project_deployment = Task(
    name='remove-deployment',
    group=project_group,
    upstreams=[]
)
runner.register(remove_project_deployment)

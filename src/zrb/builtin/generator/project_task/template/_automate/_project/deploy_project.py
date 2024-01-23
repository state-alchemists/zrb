from zrb import Task, runner
from zrb.builtin.group import project_group

deploy_project = Task(
    name="deploy",
    group=project_group,
    upstreams=[],
    description="Deploy project",
    run=lambda *args, **kwargs: kwargs.get("_task").print_out("🆗"),
)
runner.register(deploy_project)

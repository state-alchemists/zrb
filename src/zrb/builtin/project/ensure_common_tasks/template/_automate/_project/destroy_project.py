from zrb import Task, runner
from zrb.builtin.project._group import project_group

destroy_project = Task(
    name="destroy",
    group=project_group,
    upstreams=[],
    description="Remove project deployment",
    run=lambda *args, **kwargs: kwargs.get("_task").print_out("🆗"),
)
runner.register(destroy_project)

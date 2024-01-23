from zrb import Task, runner
from zrb.builtin.group import project_group

push_project_images = Task(
    name="push-images",
    group=project_group,
    upstreams=[],
    description="Build project images",
    run=lambda *args, **kwargs: kwargs.get("_task").print_out("🆗"),
)
runner.register(push_project_images)

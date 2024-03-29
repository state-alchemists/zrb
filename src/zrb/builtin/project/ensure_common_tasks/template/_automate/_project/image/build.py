from zrb import Task, runner
from ._group import project_image_group

build_project_images = Task(
    name="build",
    group=project_image_group,
    upstreams=[],
    description="Build project images",
    run=lambda *args, **kwargs: kwargs.get("_task").print_out("🆗"),
)
runner.register(build_project_images)

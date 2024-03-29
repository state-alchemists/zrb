from zrb import Task, runner
from ._group import project_image_group

push_project_images = Task(
    name="push-images",
    group=project_image_group,
    upstreams=[],
    description="Push project images",
    run=lambda *args, **kwargs: kwargs.get("_task").print_out("🆗"),
)
runner.register(push_project_images)

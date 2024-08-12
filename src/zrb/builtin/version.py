from typing import Any

from zrb.config.config import VERSION
from zrb.runner import runner
from zrb.task.decorator import python_task
from zrb.task.task import Task


@python_task(name="version", description="Get Zrb version", runner=runner)
async def get_version(*args: Any, **kwargs: Any) -> str:
    task: Task = kwargs.get("_task")
    task.print_out(VERSION)
    return VERSION

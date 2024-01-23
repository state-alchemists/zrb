from zrb.config.config import version
from zrb.helper.typing import Any
from zrb.runner import runner
from zrb.task.decorator import python_task

###############################################################################
# Task Definitions
###############################################################################


@python_task(name="version", description="Get Zrb version", runner=runner)
async def get_version(*args: Any, **kwargs: Any) -> str:
    return version

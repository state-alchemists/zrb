from typing import Any
from ..task.decorator import python_task
from ..runner import runner
from ..config.config import version

###############################################################################
# Task Definitions
###############################################################################


@python_task(
    name='version',
    description='Get Zrb version',
    runner=runner
)
async def get_version(*args: Any, **kwargs: Any) -> str:
    return version

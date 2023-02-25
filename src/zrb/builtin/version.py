from typing import Any
from ..task.task import Task
from ..runner import runner
from ..config.config import version


def _version(*args: Any, **kwargs: Any) -> str:
    return version


get_version = Task(
    name='version',
    run=_version,
    description='Get Zrb version',
)
runner.register(get_version)

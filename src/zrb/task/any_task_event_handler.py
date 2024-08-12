from collections.abc import Callable
from typing import Any

from zrb.helper.accessories.color import colored
from zrb.helper.log import logger
from zrb.task.any_task import AnyTask

logger.debug(colored("Loading zrb.task.any_task_event_handler", attrs=["dark"]))

_TaskEventHandler = Callable[[AnyTask], Any]
OnTriggered = _TaskEventHandler
OnWaiting = _TaskEventHandler
OnSkipped = _TaskEventHandler
OnStarted = _TaskEventHandler
OnReady = _TaskEventHandler
OnRetry = _TaskEventHandler
OnFailed = Callable[[AnyTask, bool, Exception], Any]

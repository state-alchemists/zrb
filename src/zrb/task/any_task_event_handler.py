from zrb.helper.typing import Any, Callable
from zrb.task.any_task import AnyTask
from zrb.helper.accessories.color import colored
from zrb.helper.log import logger

logger.info(colored("Loading zrb.task.any_ask_event_handler", attrs=["dark"]))

_TaskEventHandler = Callable[[AnyTask], Any]
OnTriggered = _TaskEventHandler
OnWaiting = _TaskEventHandler
OnSkipped = _TaskEventHandler
OnStarted = _TaskEventHandler
OnReady = _TaskEventHandler
OnRetry = _TaskEventHandler
OnFailed = Callable[[AnyTask, bool, Exception], Any]

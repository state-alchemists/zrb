from zrb.helper.typing import Any, Callable
from zrb.task.any_task import AnyTask

_TaskEventHandler = Callable[[AnyTask], Any]
OnTriggered = _TaskEventHandler
OnWaiting = _TaskEventHandler
OnSkipped = _TaskEventHandler
OnStarted = _TaskEventHandler
OnReady = _TaskEventHandler
OnRetry = _TaskEventHandler
OnFailed = Callable[[AnyTask, bool, Exception], Any]

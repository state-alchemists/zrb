from collections.abc import Callable, Mapping
from typing import Optional

from zrb.helper.accessories.color import colored
from zrb.helper.callable import run_async
from zrb.helper.log import logger

logger.debug(colored("Loading zrb.task.looper", attrs=["dark"]))


class Looper:
    def __init__(self):
        self._queue: Mapping[str, list[Optional[bool]]] = {}
        self._should_stop = False

    async def pop(self, identifier: str) -> Optional[bool]:
        if identifier not in self._queue or len(self._queue[identifier]) == 0:
            return None
        return self._queue[identifier].pop(0)

    def stop(self):
        self._should_stop = True

    def is_registered(self, identifier: str) -> bool:
        return identifier in self._queue

    async def register(self, identifier: str, function: Callable[..., Optional[bool]]):
        if identifier in self._queue:
            return
        self._queue[identifier] = []
        while not self._should_stop:
            try:
                result = await run_async(function)
                if result is not None:
                    if not result:
                        continue
                    while len(self._queue[identifier]) > 1000:
                        self._queue[identifier].pop(0)
                    self._queue[identifier].append(result)
            except KeyboardInterrupt:
                self.stop()
                break


looper = Looper()

import asyncio
import time

from zrb.helper.typecheck import typechecked
from zrb.helper.typing import Optional

LOG_NAME_LENGTH = 20


@typechecked
class TimeTracker:
    def __init__(self):
        self.__start_time: float = 0
        self.__end_time: float = 0

    def _start_timer(self):
        self.__start_time = time.time()

    def _end_timer(self):
        self.__end_time = time.time()

    def _get_elapsed_time(self) -> float:
        return self.__end_time - self.__start_time


@typechecked
class AttemptTracker:
    def __init__(self, retry: int = 2):
        self.__retry = retry
        self.__attempt: int = 1

    def _get_max_attempt(self) -> int:
        return self.__retry + 1

    def _get_attempt(self) -> int:
        return self.__attempt

    def _increase_attempt(self):
        self.__attempt += 1

    def _should_attempt(self) -> bool:
        attempt = self._get_attempt()
        max_attempt = self._get_max_attempt()
        return attempt <= max_attempt

    def _is_last_attempt(self) -> bool:
        attempt = self._get_attempt()
        max_attempt = self._get_max_attempt()
        return attempt >= max_attempt


@typechecked
class FinishTracker:
    def __init__(self):
        self.__execution_queue: Optional[asyncio.Queue] = None
        self.__counter = 0

    async def _mark_awaited(self):
        if self.__execution_queue is None:
            self.__execution_queue = asyncio.Queue()
        self.__counter += 1

    async def _mark_done(self):
        # Tracker might be started several times
        # However, when the execution is marked as done, it applied globally
        # Thus, we need to send event as much as the counter.
        for i in range(self.__counter):
            await self.__execution_queue.put(True)

    async def _is_done(self) -> bool:
        while self.__execution_queue is None:
            await asyncio.sleep(0.05)
        return await self.__execution_queue.get()

import datetime
from abc import ABC, abstractmethod

from ..session_state_log.session_state_log import SessionStateLog


class AnySessionStateLogger(ABC):

    @abstractmethod
    def write(self, session_log: SessionStateLog):
        pass

    @abstractmethod
    def read(self, session_name: str) -> SessionStateLog:
        pass

    @abstractmethod
    def list(
        self,
        task_path: list[str],
        min_start_time: datetime.datetime,
        max_start_time: datetime.datetime,
        page: int = 0,
        limit: int = 10,
    ) -> list[SessionStateLog]:
        pass

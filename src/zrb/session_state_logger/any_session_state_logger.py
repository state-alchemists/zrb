from abc import ABC, abstractmethod
from ..session_state_log.session_state_log import SessionStateLog


class AnySessionStateLogger(ABC):

    @abstractmethod
    def write(self, session_log: SessionStateLog, session_parent_name: str | None):
        pass

    @abstractmethod
    def read(self, session_name: str) -> SessionStateLog:
        pass

    @abstractmethod
    def read_children(self, session_name: str, page: int) -> list[SessionStateLog]:
        pass

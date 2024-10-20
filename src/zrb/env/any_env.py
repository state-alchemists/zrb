from abc import ABC, abstractmethod
from ..session.session import Session


class AnyEnv(ABC):
    @abstractmethod
    def update_session(self, session: Session):
        pass

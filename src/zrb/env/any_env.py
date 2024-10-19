from collections.abc import Mapping
from abc import ABC, abstractmethod
from ..session.session import Session


class AnyEnv(ABC):
    @abstractmethod
    def get_env_map(self, session: Session) -> Mapping[str, str]:
        pass

from typing import Any
from abc import ABC, abstractmethod
from ..session.session import Session


class AnyInput(ABC):
    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def get_prompt(self) -> str:
        pass

    @abstractmethod
    def get_value(self, session: Session, value: Any = None) -> Any:
        pass

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
    def get_prompt_message(self) -> str:
        pass

    @abstractmethod
    def get_default_value(self, session: Session) -> Any:
        pass

    @abstractmethod
    def allow_positional_argument(self) -> bool:
        pass

    @abstractmethod
    def update_session(self, session: Session, value: Any = None):
        pass

    @abstractmethod
    def prompt_cli(self, session: Session) -> Any:
        pass

from abc import ABC, abstractmethod


class AnyCustomCommand(ABC):

    @property
    @abstractmethod
    def command(self) -> str:
        """Command"""

    @property
    @abstractmethod
    def description(self) -> str:
        """Description"""

    @property
    @abstractmethod
    def args(self) -> list[str]:
        """Command"""

    @abstractmethod
    def get_prompt(self, kwargs: dict[str, str]) -> str:
        """Return the prompt"""

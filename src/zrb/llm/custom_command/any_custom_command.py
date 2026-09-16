from abc import ABC, abstractmethod


class AnyCustomCommand(ABC):

    @property
    @abstractmethod
    def command(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def args(self) -> list[str]: ...

    @abstractmethod
    def get_prompt(self, kwargs: dict[str, str]) -> str: ...

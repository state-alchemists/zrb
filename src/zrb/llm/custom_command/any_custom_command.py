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

    def handle(self, kwargs: dict[str, str]) -> str | None:
        """Run the command in-process instead of prompting the LLM.

        Return ``None`` (the default) to send ``get_prompt(kwargs)`` to the
        LLM. Return a string to handle the command here: it is shown to the
        user (nothing is shown for ``""``) and no LLM turn starts.
        """
        return None

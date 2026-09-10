from abc import ABC, abstractmethod

from zrb.context.any_context import AnyContext


class AnyCmdVal(ABC):
    """A shell command resolved against a task context at run time."""

    @abstractmethod
    def to_str(self, ctx: AnyContext) -> str:
        """Resolve this value into the command string to execute."""

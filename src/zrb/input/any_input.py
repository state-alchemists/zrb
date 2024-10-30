from abc import ABC, abstractmethod
from ..context.shared_context import SharedContext


class AnyInput(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def prompt_message(self) -> str:
        pass

    @abstractmethod
    def to_html(self, shared_ctx: SharedContext) -> str:
        pass

    @abstractmethod
    def update_shared_context(self, shared_ctx: SharedContext, str_value: str | None = None):
        pass

    @abstractmethod
    def prompt_cli_str(self, shared_ctx: SharedContext) -> str:
        pass

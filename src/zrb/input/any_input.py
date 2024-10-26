from typing import Any
from abc import ABC, abstractmethod
from ..context.shared_context import SharedContext


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
    def get_default_value(self, shared_ctx: SharedContext) -> Any:
        pass

    @abstractmethod
    def allow_positional_argument(self) -> bool:
        pass

    @abstractmethod
    def update_shared_context(self, shared_ctx: SharedContext, value: Any = None):
        pass

    @abstractmethod
    def prompt_cli(self, shared_ctx: SharedContext) -> Any:
        pass

from abc import ABC, abstractmethod

from zrb.context.any_shared_context import AnySharedContext


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
    def always_prompt(self) -> bool:
        pass

    @property
    @abstractmethod
    def prompt_message(self) -> str:
        pass

    @property
    @abstractmethod
    def allow_positional_parsing(self) -> bool:
        pass

    @abstractmethod
    def to_html(self, shared_ctx: AnySharedContext) -> str:
        pass

    @abstractmethod
    def update_shared_context(
        self, shared_ctx: AnySharedContext, str_value: str | None = None
    ):
        pass

    @abstractmethod
    def prompt_cli_str(self, shared_ctx: AnySharedContext) -> str:
        pass

    @abstractmethod
    def get_default_str(self, shared_ctx: AnySharedContext) -> str:
        pass

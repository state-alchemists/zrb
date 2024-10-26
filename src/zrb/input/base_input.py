from typing import Any
from ..attr.type import StrAttr
from ..context.shared_context import SharedContext
from ..util.attr import get_str_attr
from .any_input import AnyInput


class BaseInput(AnyInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_str: StrAttr = "",
        auto_render: bool = True,
        allow_empty: bool = True,
        allow_positional_argument: bool = True,
    ):
        self._name = name
        self._description = description
        self._prompt = prompt
        self._default_str = default_str
        self._auto_render = auto_render
        self._allow_empty = allow_empty
        self._allow_positional_argument = allow_positional_argument

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._description if self._description is not None else self.get_name()

    def get_prompt_message(self) -> str:
        return self._prompt if self._prompt is not None else self.get_name()

    def allow_positional_argument(self) -> bool:
        return self._allow_positional_argument

    def update_shared_context(self, shared_ctx: SharedContext, value: Any = None):
        if value is None:
            value = self.get_default_value(shared_ctx)
        shared_ctx.input[self.get_name()] = value

    def prompt_cli(self, shared_ctx: SharedContext) -> str:
        value = self._prompt_cli_once(shared_ctx)
        while not self._allow_empty and value == "":
            value = self._prompt_cli_once(shared_ctx)
        return value

    def _prompt_cli_once(self, shared_ctx: SharedContext) -> str:
        prompt_message = self.get_prompt_message()
        default_value = self._get_default_str(shared_ctx)
        if default_value != "":
            prompt_message = f"{prompt_message} [{default_value}]"
        value = input(f"{prompt_message}: ")
        if value.strip() == "":
            value = default_value
        return value

    def get_default_value(self, shared_ctx: SharedContext) -> str:
        return self._get_default_str(shared_ctx)

    def _get_default_str(self, shared_ctx: SharedContext) -> str:
        return get_str_attr(shared_ctx, self._default_str, auto_render=self._auto_render)

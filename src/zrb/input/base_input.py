from typing import Any
from collections.abc import Callable
from ..session.shared_context import SharedContext
from .any_input import AnyInput


class BaseInput(AnyInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: Any | Callable[[SharedContext], Any] = None,
        auto_render: bool = True,
        allow_empty: bool = True,
        allow_positional_argument: bool = True,
    ):
        self._name = name
        self._description = description
        self._prompt = prompt
        self._default_value = default
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

    def update_shared_context(self, shared_context: SharedContext, value: Any = None):
        if value is None:
            value = self.get_default_value(shared_context)
        shared_context.inputs[self.get_name()] = value

    def prompt_cli(self, shared_context: SharedContext) -> Any:
        value = self._prompt_cli(shared_context)
        while not self._allow_empty and (value == "" or value is None):
            value = self._prompt_cli(shared_context)
        return value

    def _prompt_cli(self, shared_context: SharedContext) -> Any:
        prompt_message = self.get_prompt_message()
        default_value = self.get_default_value(shared_context)
        if default_value is not None:
            prompt_message = f"{prompt_message} [{default_value}]"
        value = input(f"{prompt_message}: ")
        if value.strip() == "":
            value = default_value
        return value

    def get_default_value(self, shared_context: SharedContext) -> Any:
        if callable(self._default_value):
            return self._default_value(shared_context)
        if self._auto_render and isinstance(self._default_value, str):
            return shared_context.render(self._default_value)
        return self._default_value

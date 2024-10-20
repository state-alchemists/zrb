from typing import Any
from collections.abc import Callable
from ..session.session import Session
from .any_input import AnyInput


class BaseInput(AnyInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: Any | Callable[[Session], Any] = None,
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

    def update_session(self, session: Session, value: Any = None):
        if value is None:
            value = self.get_default_value(session)
        session.inputs[self.get_name()] = value

    def prompt_cli(self, session: Session) -> Any:
        value = self._prompt_cli(session)
        while not self._allow_empty and (value == "" or value is None):
            value = self._prompt_cli(session)
        return value

    def _prompt_cli(self, session: Session) -> Any:
        prompt_message = self.get_prompt_message()
        default_value = self.get_default_value(session)
        if default_value is not None:
            prompt_message = f"{prompt_message} [{default_value}]"
        value = input(f"{prompt_message}: ")
        if value.strip() == "":
            value = default_value
        return value

    def get_default_value(self, session: Session) -> Any:
        default_value = self._get_default_value(session)
        if self._auto_render and isinstance(default_value, str):
            session.render(default_value)
        return default_value

    def _get_default_value(self, session: Session) -> Any:
        if callable(self._default_value):
            return self._default_value(session)
        return self._default_value

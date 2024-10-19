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
        default_value: Any | Callable[[Session], Any] = None,
        auto_render: bool = True,
    ):
        self._name = name
        self._description = description
        self._prompt = prompt
        self._default_value = default_value
        self._auto_render = auto_render

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._description if self._description is not None else self.get_name()

    def get_prompt(self) -> str:
        return self._prompt if self._prompt is not None else self.get_name()

    def get_default_value(self, session: Session) -> Any:
        default_value = self._get_default_value()
        if self._auto_render and isinstance(default_value, str):
            session.render(default_value)
        return default_value

    def _get_default_value(self, session: Session) -> Any:
        if callable(self._default_value):
            return self._default_value(session)
        return self._default_value

    def get_value(self, session: Session, value: Any = None) -> Any:
        if value is None:
            return self._get_default_value(session)
        return value

from typing import Any
from .base_input import BaseInput
from collections.abc import Callable
from ..session.session import Session


class StrInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: str | Callable[[Session], str] = "",
        auto_render: bool = True,
        allow_empty: bool = True,
        allow_positional_argument: bool = True,
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default=default,
            auto_render=auto_render,
            allow_empty=allow_empty,
            allow_positional_argument=allow_positional_argument,
        )

    def update_session(self, session: Session, value: Any = None) -> str:
        return super().update_session(session, value)

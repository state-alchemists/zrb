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
        default_value: str | Callable[[Session], str] = "",
        auto_render: bool = True,
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default_value=default_value,
            auto_render=auto_render
        )

    def get_value(self, session: Session, value: Any = None) -> str:
        return super().get_value(session, value)

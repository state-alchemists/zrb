from typing import Any
from .base_input import BaseInput
from collections.abc import Callable
from ..session.session import Session


class IntInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_value: str | int | Callable[[Session], str] = 0,
        auto_render: bool = True,
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default_value=default_value,
            auto_render=auto_render
        )

    def get_value(self, session: Session, value: Any = None) -> int:
        return int(super().get_value(session, value))

from typing import Any
from .base_input import BaseInput
from collections.abc import Callable
from ..session.shared_context import SharedContext


class StrInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: str | Callable[[SharedContext], str] = "",
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

    def update_shared_context(
        self, shared_context: SharedContext, value: Any = None
    ) -> str:
        return super().update_shared_context(shared_context, value)

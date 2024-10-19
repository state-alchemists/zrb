from .str_input import StrInput
from collections.abc import Callable
from ..session.session import Session


class PasswordInput(StrInput):
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
        self._is_secret = True

from .base_input import BaseInput
from collections.abc import Callable
from ..session.session import Session


class IntInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: str | int | Callable[[Session], str] = 0,
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

    def update_session(self, session: Session, value: str | int | None = None):
        if value is None:
            value = self.get_default_value(session)
        value = int(value)
        super().update_session(session, value)

    def get_default_value(self, session: Session) -> int:
        return int(super().get_default_value(session))

    def prompt_cli(self, session: Session) -> int:
        return int(super().prompt_cli(session))

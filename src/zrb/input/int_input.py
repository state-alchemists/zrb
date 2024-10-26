from .base_input import BaseInput
from collections.abc import Callable
from ..context.shared_context import SharedContext


class IntInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: str | int | Callable[[SharedContext], str] = 0,
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
        self, shared_ctx: SharedContext, value: str | int | None = None
    ):
        if value is None:
            value = self.get_default_value(shared_ctx)
        value = int(value)
        super().update_shared_context(shared_ctx, value)

    def get_default_value(self, shared_ctx: SharedContext) -> int:
        return int(super().get_default_value(shared_ctx))

    def prompt_cli(self, shared_ctx: SharedContext) -> int:
        return int(super().prompt_cli(shared_ctx))

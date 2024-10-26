from .base_input import BaseInput
from ..attr.type import StrAttr
from ..context.shared_context import SharedContext
from ..util.string.conversion import to_boolean


class IntInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_str: StrAttr = "False",
        auto_render: bool = True,
        allow_empty: bool = True,
        allow_positional_argument: bool = True,
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default_str=default_str,
            auto_render=auto_render,
            allow_empty=allow_empty,
            allow_positional_argument=allow_positional_argument,
        )

    def prompt_cli(self, shared_ctx: SharedContext) -> bool:
        return to_boolean(super().prompt_cli(shared_ctx))

    def get_default_value(self, shared_ctx: SharedContext) -> bool:
        return to_boolean(super().get_default_value(shared_ctx))

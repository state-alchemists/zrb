from typing import Any
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
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default_str=default_str,
            auto_render=auto_render,
            allow_empty=allow_empty,
        )
    
    def _parse_str_value(self, str_value: str) -> bool:
        return to_boolean(str_value)

from .base_input import BaseInput
from ..attr.type import StrAttr
from ..context.shared_context import SharedContext


class FloatInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_str: StrAttr = "0.0",
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
 
    def _parse_str_value(self, str_value: str) -> float:
        return float(str_value)
   
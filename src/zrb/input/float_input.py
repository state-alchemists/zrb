from .base_input import BaseInput
from ..context.shared_context import SharedContext
from ..attr.type import StrAttr


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

    def to_html(self, ctx: SharedContext) -> str:
        name = self.name
        description = self.description
        default = self._get_default_str(ctx)
        return f'<input type="number" name="{name}" placeholder="{description}" value="{default}" />'  # noqa

    def _parse_str_value(self, str_value: str) -> float:
        return float(str_value)

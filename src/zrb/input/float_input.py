from zrb.attr.type import FloatAttr
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.base_input import BaseInput
from zrb.util.attr import get_float_attr


class FloatInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: FloatAttr = 0.0,
        auto_render: bool = True,
        allow_empty: bool = False,
        allow_positional_parsing: bool = True,
        always_prompt: bool = True,
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default=default,
            auto_render=auto_render,
            allow_empty=allow_empty,
            allow_positional_parsing=allow_positional_parsing,
            always_prompt=always_prompt,
        )

    def to_html(self, shared_ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = self.get_default_str(shared_ctx)
        return f'<input type="number" name="{name}" placeholder="{description}" value="{default}" step="any" />'  # noqa

    def get_default_str(self, shared_ctx: AnySharedContext) -> str:
        default_value = get_float_attr(
            shared_ctx, self._default_value, auto_render=self._auto_render
        )
        return f"{default_value}"

    def _parse_str_value(self, str_value: str) -> float:
        return float(str_value)

from zrb.attr.type import BoolAttr
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.base_input import BaseInput
from zrb.util.attr import get_bool_attr
from zrb.util.string.conversion import to_boolean


class BoolInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: BoolAttr = False,
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
        default = to_boolean(self.get_default_str(shared_ctx))
        selected_true = "selected" if default else ""
        selected_false = "selected" if not default else ""
        return "\n".join(
            [
                f'<select name="{name}" placeholder="{description}">',
                f'<option value="true" {selected_true}>true</option>',
                f'<option value="false" {selected_false}>false</option>',
                "</select>",
            ]
        )

    def get_default_str(self, shared_ctx: AnySharedContext) -> str:
        default_value = get_bool_attr(
            shared_ctx, self._default_value, auto_render=self._auto_render
        )
        return f"{default_value}"

    def _parse_str_value(self, str_value: str) -> bool:
        return to_boolean(str_value)

from zrb.attr.type import StrAttr
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.base_input import BaseInput
from zrb.util.string.conversion import to_boolean


class BoolInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_str: StrAttr = "False",
        auto_render: bool = True,
        allow_empty: bool = False,
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default_str=default_str,
            auto_render=auto_render,
            allow_empty=allow_empty,
        )

    def to_html(self, ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = to_boolean(self._get_default_str(ctx))
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

    def _parse_str_value(self, str_value: str) -> bool:
        return to_boolean(str_value)

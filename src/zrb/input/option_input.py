from zrb.attr.type import StrAttr, StrListAttr
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.base_input import BaseInput
from zrb.util.attr import get_str_list_attr


class OptionInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        options: StrListAttr = [],
        default_str: StrAttr = "",
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
        self._options = options

    def to_html(self, ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = self._get_default_str(ctx)
        html = [f'<select name="{name}" placeholder="{description}">']
        for value in get_str_list_attr(ctx, self._options, self._auto_render):
            selected = "selected" if value == default else ""
            html.append(f'<option value="{value}" {selected}>{value}</option>')
        html.append("</select>")
        return "\n".join(html)

    def _prompt_cli_str(self, shared_ctx: AnySharedContext) -> str:
        prompt_message = self.prompt_message
        default_value = self._get_default_str(shared_ctx)
        options = get_str_list_attr(shared_ctx, self._options, self._auto_render)
        option_str = ", ".join(options)
        if default_value != "":
            prompt_message = f"{prompt_message} ({option_str}) [{default_value}]"
        value = input(f"{prompt_message}: ")
        if value.strip() != "" and value.strip() not in options:
            value = self._prompt_cli_str(shared_ctx)
        if value.strip() == "":
            value = default_value
        return value

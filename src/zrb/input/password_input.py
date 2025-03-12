import getpass

from zrb.attr.type import StrAttr
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.base_input import BaseInput


class PasswordInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: StrAttr = "",
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
        self._is_secret = True

    def to_html(self, shared_ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = self.get_default_str(shared_ctx)
        return f'<input type="password" name="{name}" placeholder="{description}" value="{default}" />'  # noqa

    def _prompt_cli_str(self, shared_ctx: AnySharedContext) -> str:
        prompt_message = self.prompt_message
        default_value = self.get_default_str(shared_ctx)
        value = getpass.getpass(f"{prompt_message}: ")
        if value.strip() == "":
            value = default_value
        return value

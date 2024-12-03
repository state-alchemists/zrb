import getpass
from collections.abc import Callable

from zrb.context.any_shared_context import AnySharedContext
from zrb.input.base_input import BaseInput


class PasswordInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_str: str | Callable[[AnySharedContext], str] = "",
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
        self._is_secret = True

    def to_html(self, ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = self._get_default_str(ctx)
        return f'<input type="password" name="{name}" placeholder="{description}" value="{default}" />'  # noqa

    def _prompt_cli_str(self, shared_ctx: AnySharedContext) -> str:
        prompt_message = self.prompt_message
        default_value = self._get_default_str(shared_ctx)
        value = getpass.getpass(f"{prompt_message}: ")
        if value.strip() == "":
            value = default_value
        return value

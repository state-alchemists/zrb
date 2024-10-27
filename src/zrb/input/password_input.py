from .base_input import BaseInput
from collections.abc import Callable
from ..context.shared_context import SharedContext
import getpass


class PasswordInput(BaseInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_str: str | Callable[[SharedContext], str] = "",
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
        self._is_secret = True

    def _prompt_cli_str(self, shared_ctx: SharedContext) -> str:
        prompt_message = self.get_prompt_message()
        default_value = self._get_default_str_value(shared_ctx)
        value = getpass.getpass(f"{prompt_message}: ")
        if value.strip() == "":
            value = default_value
        return value

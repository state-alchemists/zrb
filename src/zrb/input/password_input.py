from .str_input import StrInput
from collections.abc import Callable
from ..session.shared_context import SharedContext
import getpass


class PasswordInput(StrInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default: str | Callable[[SharedContext], str] = "",
        auto_render: bool = True,
        allow_empty: bool = True,
        allow_positional_argument: bool = True,
    ):
        super().__init__(
            name=name,
            description=description,
            prompt=prompt,
            default=default,
            auto_render=auto_render,
            allow_empty=allow_empty,
            allow_positional_argument=allow_positional_argument,
        )
        self._is_secret = True

    def _prompt_cli(self, shared_context: SharedContext) -> str:
        prompt_message = self.get_prompt_message()
        default_value = self.get_default_value(shared_context)
        value = getpass.getpass(f"{prompt_message}: ")
        if value.strip() == "":
            value = default_value
        return value

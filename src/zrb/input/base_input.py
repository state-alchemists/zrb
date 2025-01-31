from typing import Any

from zrb.attr.type import StrAttr
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.any_input import AnyInput
from zrb.util.attr import get_str_attr
from zrb.util.string.conversion import to_snake_case


class BaseInput(AnyInput):
    def __init__(
        self,
        name: str,
        description: str | None = None,
        prompt: str | None = None,
        default_str: StrAttr = "",
        auto_render: bool = True,
        allow_empty: bool = False,
        allow_positional_parsing: bool = True,
    ):
        self._name = name
        self._description = description
        self._prompt = prompt
        self._default_str = default_str
        self._auto_render = auto_render
        self._allow_empty = allow_empty
        self._allow_positional_parsing = allow_positional_parsing

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self._name}>"

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description if self._description is not None else self.name

    @property
    def prompt_message(self) -> str:
        return self._prompt if self._prompt is not None else self.name

    @property
    def allow_positional_parsing(self) -> bool:
        return self._allow_positional_parsing

    def to_html(self, ctx: AnySharedContext) -> str:
        name = self.name
        description = self.description
        default = self.get_default_str(ctx)
        return f'<input name="{name}" placeholder="{description}" value="{default}" />'

    def update_shared_context(
        self, shared_ctx: AnySharedContext, str_value: str | None = None
    ):
        if str_value is None:
            str_value = self.get_default_str(shared_ctx)
        value = self._parse_str_value(str_value)
        if self.name in shared_ctx.input:
            raise ValueError(f"Input already defined in the context: {self.name}")
        shared_ctx.input[self.name] = value
        # We want to be able to access ctx.input["project-name"] as
        # ctx.input.project_name
        snake_key = to_snake_case(self.name)
        if snake_key == self.name:
            return
        if snake_key in shared_ctx.input:
            raise ValueError("Input already defined in the context: {snake_key}")
        shared_ctx.input[snake_key] = value

    def _parse_str_value(self, str_value: str) -> Any:
        """Override this to transform str_value"""
        return str_value

    def prompt_cli_str(self, shared_ctx: AnySharedContext) -> str:
        value = self._prompt_cli_str(shared_ctx)
        while not self._allow_empty and value == "":
            value = self._prompt_cli_str(shared_ctx)
        return value

    def _prompt_cli_str(self, shared_ctx: AnySharedContext) -> str:
        prompt_message = self.prompt_message
        default_value = self.get_default_str(shared_ctx)
        if default_value != "":
            prompt_message = f"{prompt_message} [{default_value}]"
        print(f"{prompt_message}: ", end="")
        value = input()
        if value.strip() == "":
            value = default_value
        return value

    def get_default_str(self, shared_ctx: AnySharedContext) -> str:
        return get_str_attr(
            shared_ctx, self._default_str, auto_render=self._auto_render
        )

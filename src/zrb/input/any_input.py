"""Interface every Zrb task input implements.

Docstrings here are the contract. `inspect.getdoc` walks the MRO, so concrete
inputs (`StrInput`, `BoolInput`, ...) inherit these descriptions and only need
their own docstring where behaviour actually differs.
"""

from abc import ABC, abstractmethod
from typing import Any

from zrb.context.any_shared_context import AnySharedContext


class AnyInput(ABC):
    """An input a task prompts for, parses, and exposes on the context.

    Implementations decide how a raw string becomes a typed value and how the
    input renders on the CLI and in the web UI.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The input's name.

        Doubles as the CLI flag (`--name`) and the context key. It is also
        exposed on the context in snake_case, so `project-name` is readable as
        `ctx.input.project_name`.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """Help text shown beside the input, falling back to its name."""

    @property
    @abstractmethod
    def always_prompt(self) -> bool:
        """Whether to prompt even when a default is available."""

    @property
    @abstractmethod
    def prompt_message(self) -> str:
        """The message shown when prompting, falling back to the name."""

    @property
    @abstractmethod
    def allow_positional_parsing(self) -> bool:
        """Whether this input can be supplied as a bare positional argument.

        When False it must be passed as `--name value`.
        """

    @abstractmethod
    def to_html(self, shared_ctx: AnySharedContext) -> str:
        """Render this input as an HTML form control for the web UI.

        Implementations must HTML-escape every interpolated value.
        """

    @abstractmethod
    def update_shared_context(
        self,
        shared_ctx: AnySharedContext,
        str_value: str | None = None,
        value: Any = None,
    ):
        """Parse a value and record it on the shared context.

        Args:
            shared_ctx: Context to write to.
            str_value: Raw string to parse. Ignored when `value` is given;
                falls back to the rendered default when both are omitted.
            value: An already-typed value, stored without parsing.

        Raises:
            ValueError: If this input is already set on the context.
        """

    @abstractmethod
    def prompt_cli_str(self, shared_ctx: AnySharedContext) -> str:
        """Prompt on the terminal and return the raw string entered.

        Re-prompts while the entry is empty, unless the input allows empty
        values. The result is still unparsed — pass it to
        `update_shared_context` to type it.
        """

    @abstractmethod
    def get_default_str(self, shared_ctx: AnySharedContext) -> str:
        """Resolve this input's default as a string.

        Templated defaults are rendered against `shared_ctx` when the input was
        built with `auto_render`; non-string defaults are coerced with `str`.
        """

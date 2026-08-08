from __future__ import annotations  # Enables forward references

import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TextIO

from zrb.dot_dict.dot_dict import DotDict

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core import CoreSchema

    from zrb.session import any_session


# Note: __get_pydantic_core_schema__ and __get_pudantic_json_schema__ is needed
# since session generate state_log (which is a pydantic base model)
class AnySharedContext(ABC):
    """Abstract base class for shared context across tasks.

    This class provides methods to manage shared settings and utilities,
    such as logging level configuration, time display preferences, and
    rendering templates with additional data.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: "GetCoreSchemaHandler"
    ) -> "CoreSchema":
        # lazy: heavy third-party
        from pydantic_core import core_schema

        return core_schema.is_instance_schema(cls)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: "CoreSchema", handler: "GetJsonSchemaHandler"
    ) -> "JsonSchemaValue":
        return {"type": "object", "title": "AnySharedContext"}

    @property
    @abstractmethod
    def is_web_mode(self) -> bool:
        """Whether the session is driven by the web UI rather than the CLI.

        Use it to skip prompts and terminal-only output.
        """

    @property
    @abstractmethod
    def is_tty(self) -> bool:
        """Whether output is attached to an interactive terminal.

        False when piped or redirected, so avoid colors and progress spinners.
        """

    @property
    @abstractmethod
    def input(self) -> DotDict:
        """Resolved input values, by input name.

        Also keyed in snake_case, so `ctx.input.project_name` reaches the input
        named `project-name`.
        """

    @property
    @abstractmethod
    def env(self) -> DotDict:
        """Environment variables visible to this session, by name."""

    @property
    @abstractmethod
    def args(self) -> list[Any]:
        """Positional CLI arguments left over after inputs were parsed."""

    @property
    @abstractmethod
    def xcom(self) -> DotDict:
        """Cross-task message queues, keyed by task name.

        Each value is an `Xcom` queue: a task pushes results others pop. This
        is the supported way to pass data between tasks.
        """

    @property
    @abstractmethod
    def shared_log(self) -> list[str]:
        """Every log line emitted in this session, across all tasks."""

    @property
    @abstractmethod
    def session(self) -> any_session.AnySession | None:
        """The session owning this context, once one is bound."""

    @abstractmethod
    def append_to_shared_log(self, message: str):
        """Append one line to the session-wide log."""

    @abstractmethod
    def set_session(self, session: any_session.AnySession):
        """Bind this context to `session`.

        Called by the execution layer during setup; task code should not need
        to call it.
        """

    @abstractmethod
    def get_logging_level(self) -> int:
        """Retrieves the current logging level.

        Returns:
            int: The logging level to be used, typically corresponding to
            standard logging levels such as logging.DEBUG, loggin.INFO, logging.WARNING, etc.
        """
        pass

    @abstractmethod
    def render(self, template: str) -> str:
        """Renders a template string with optional additional data.

        Args:
            template (str): The template string to be rendered.

        Returns:
            str: The rendered template as a string.
        """
        pass

    @abstractmethod
    def shared_print(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True,
    ):
        """Print without any task prefix, and record the line in `shared_log`.

        Session-level counterpart to `AnyContext.print`, which prefixes each
        line with its task's name and icon. Signature mirrors the builtin
        `print`, except output defaults to stderr so it never pollutes piped
        stdout.
        """

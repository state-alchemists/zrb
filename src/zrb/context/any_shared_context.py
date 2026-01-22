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
        pass

    @property
    @abstractmethod
    def is_tty(self) -> bool:
        pass

    @property
    @abstractmethod
    def input(self) -> DotDict:
        pass

    @property
    @abstractmethod
    def env(self) -> DotDict:
        pass

    @property
    @abstractmethod
    def args(self) -> list[Any]:
        pass

    @property
    @abstractmethod
    def xcom(self) -> DotDict:
        pass

    @property
    @abstractmethod
    def shared_log(self) -> list[str]:
        pass

    @property
    @abstractmethod
    def session(self) -> any_session.AnySession | None:
        pass

    @abstractmethod
    def append_to_shared_log(self, message: str):
        pass

    @abstractmethod
    def set_session(self, session: any_session.AnySession):
        pass

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
        pass

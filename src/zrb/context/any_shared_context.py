from __future__ import annotations  # Enables forward references

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from zrb.dot_dict.dot_dict import DotDict
from zrb.xcom.xcom import Xcom

if TYPE_CHECKING:
    from zrb.session import any_session


class AnySharedContext(ABC):
    """Abstract base class for shared context across tasks.

    This class provides methods to manage shared settings and utilities,
    such as logging level configuration, time display preferences, and
    rendering templates with additional data.
    """

    @property
    def input(self) -> DotDict:
        pass

    @property
    def env(self) -> DotDict:
        pass

    @property
    def args(self) -> list[Any]:
        pass

    @property
    def xcom(self) -> DotDict[str, Xcom]:
        pass

    @property
    def shared_log(self) -> list[str]:
        pass

    @property
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

from typing import Any
from abc import ABC, abstractmethod
from ..dot_dict.dot_dict import DotDict
from ..xcom.xcom import Xcom


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

    @abstractmethod
    def get_logging_level(self) -> int:
        """Retrieves the current logging level.

        Returns:
            int: The logging level to be used, typically corresponding to
            standard logging levels such as logging.DEBUG, loggin.INFO, logging.WARNING, etc.
        """
        pass

    @abstractmethod
    def should_show_time(self) -> bool:
        """Indicates whether time should be displayed in logs or other outputs.

        Returns:
            bool: True if time should be displayed, False otherwise.
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

from typing import Any
from abc import ABC, abstractmethod
from collections.abc import Mapping


class AnySharedContext(ABC):
    """Abstract base class for shared context across tasks.

    This class provides methods to manage shared settings and utilities, 
    such as logging level configuration, time display preferences, and 
    rendering templates with additional data.
    """

    @abstractmethod
    def get_logging_level(self) -> int:
        """Retrieves the current logging level.

        Returns:
            int: The logging level to be used, typically corresponding to 
            standard logging levels such as DEBUG, INFO, WARN, etc.
        """
        pass

    @abstractmethod
    def show_time(self) -> bool:
        """Indicates whether time should be displayed in logs or other outputs.

        Returns:
            bool: True if time should be displayed, False otherwise.
        """
        pass

    @abstractmethod
    def render(self, template: str, additional_data: Mapping[str, Any] = {}) -> str:
        """Renders a template string with optional additional data.

        Args:
            template (str): The template string to be rendered.
            additional_data (Mapping[str, Any], optional): Additional data 
            to be merged into the template rendering context.

        Returns:
            str: The rendered template as a string.
        """
        pass

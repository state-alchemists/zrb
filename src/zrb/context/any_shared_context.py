from typing import Any
from abc import ABC, abstractmethod
from collections.abc import Mapping
from ..dict_to_object.dict_to_object import DictToObject


class AnySharedContext(ABC):
    """Abstract base class for shared context across tasks.

    This class provides methods to manage shared settings and utilities,
    such as logging level configuration, time display preferences, and
    rendering templates with additional data.
    """

    @property
    def input(self) -> DictToObject:
        pass

    @property
    def env(self) -> DictToObject:
        pass

    @property
    def args(self) -> list[Any]:
        pass

    @property
    def xcom(self) -> DictToObject:
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

    @abstractmethod
    def render_bool(self, template: str, additional_data: Mapping[str, Any] = {}) -> bool:
        """Renders a template string with optional additional data into boolean.

        Args:
            template (str): The template string to be rendered.
            additional_data (Mapping[str, Any], optional): Additional data 
            to be merged into the template rendering context.

        Returns:
            bool: The rendered template as a boolean.
        """
        pass

    @abstractmethod
    def render_int(self, template: str, additional_data: Mapping[str, Any] = {}) -> int:
        """Renders a template string with optional additional data into integer.

        Args:
            template (str): The template string to be rendered.
            additional_data (Mapping[str, Any], optional): Additional data 
            to be merged into the template rendering context.

        Returns:
            int: The rendered template as a integer.
        """
        pass

    @abstractmethod
    def render_float(self, template: str, additional_data: Mapping[str, Any] = {}) -> float:
        """Renders a template string with optional additional data into float.

        Args:
            template (str): The template string to be rendered.
            additional_data (Mapping[str, Any], optional): Additional data 
            to be merged into the template rendering context.

        Returns:
            float: The rendered template as a float.
        """
        pass

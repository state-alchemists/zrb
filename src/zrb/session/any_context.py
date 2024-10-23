from abc import ABC, abstractmethod
from typing import Any, TextIO
from collections.abc import Mapping
import sys


class AnyContext(ABC):
    """Abstract base class for managing task contexts, logging, and rendering.

    This class provides methods for managing context-specific data such as
    attempt counts, logging, and rendering templates with additional data.
    Subclasses must implement all abstract methods.
    """

    @abstractmethod
    def set_attempt(self, attempt: int):
        """Sets the current attempt count.

        Args:
            attempt (int): The current attempt count.
        """
        pass

    @abstractmethod
    def set_max_attempt(self, max_attempt: int):
        """Sets the maximum number of attempts.

        Args:
            max_attempt (int): The maximum number of attempts allowed.
        """
        pass

    @abstractmethod
    def render(self, template: str, additional_data: Mapping[str, Any] = {}):
        """Renders the given template with additional data.

        Args:
            template (str): The template string to be rendered.
            additional_data (Mapping[str, Any], optional): Additional data to
                include in the rendering context. Defaults to an empty dict.
        """
        pass

    @abstractmethod
    def print(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        """Prints values to the specified output stream.

        Args:
            *values (object): The values to be printed.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to print to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
        pass

    @abstractmethod
    def log_debug(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        """Logs debug-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
        pass

    @abstractmethod
    def log_info(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        """Logs info-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
        pass

    @abstractmethod
    def log_warning(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        """Logs warning-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
        pass

    @abstractmethod
    def log_error(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        """Logs error-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
        pass

    @abstractmethod
    def log_critical(
        self,
        *values: object,
        sep: str | None = " ",
        end: str | None = "\n",
        file: TextIO | None = sys.stderr,
        flush: bool = True
    ):
        """Logs critical-level messages.

        Args:
            *values (object): The values to be logged.
            sep (str, optional): Separator to use between values. Defaults to a space.
            end (str, optional): String appended after the last value. Defaults to a newline.
            file (TextIO, optional): The output stream to log to. Defaults to sys.stderr.
            flush (bool, optional): Whether to flush the output stream. Defaults to True.
        """
        pass
